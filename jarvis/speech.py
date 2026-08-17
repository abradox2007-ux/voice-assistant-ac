"""jarvis/speech.py — Thread-safe, single-threaded queued text-to-speech engine."""

from __future__ import annotations

import os
import queue
import subprocess
import threading
import pyttsx3

# Thread-safe queue to pass text and done events to the TTS thread
_speech_queue: queue.Queue[tuple[str, threading.Event | None] | None] = queue.Queue()

_speaking_event = threading.Event()


def is_speaking() -> bool:
    """Return True if the assistant is currently speaking."""
    return _speaking_event.is_set()


def _tts_worker() -> None:
    """Dedicated background thread to handle SAPI/Piper initialization and speech tasks sequentially."""
    try:
        import comtypes
        comtypes.CoInitialize()
    except Exception:
        pass

    # Load configuration
    from jarvis.utils import load_config
    try:
        config = load_config()
    except Exception:
        config = {}

    tts_engine = config.get("tts_engine", "google").lower()
    piper_path = config.get("piper_path")
    piper_model = config.get("piper_model")

    # Initialize PyAudio if Piper is configured
    p_audio = None
    pyaudio = None
    if tts_engine == "piper" and piper_path and piper_model:
        try:
            import pyaudio
            p_audio = pyaudio.PyAudio()
        except Exception as e:
            print(f"[speech] Failed to initialize PyAudio: {e}")

    # Initialize pyttsx3 as fallback SAPI engine
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", 170)
        engine.setProperty("volume", 1.0)
    except Exception as exc:
        print(f"[speech] Failed to initialize fallback TTS engine: {exc}")
        engine = None

    while True:
        item = _speech_queue.get()
        if item is None:
            break
        text, done_event = item

        _speaking_event.set()

        try:
            spoken_via_piper = False
            if tts_engine == "piper" and p_audio is not None and pyaudio is not None and piper_path and piper_model:
                if os.path.exists(piper_path) and os.path.exists(piper_model):
                    try:
                        command = [
                            str(piper_path),
                            "--model", str(piper_model),
                            "--output-raw"
                        ]
                        process = subprocess.Popen(
                            command,
                            stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL
                        )
                        audio_data, _ = process.communicate(input=text.encode("utf-8"))
                        
                        if len(audio_data) > 0:
                            stream = p_audio.open(
                                format=pyaudio.paInt16,
                                channels=1,
                                rate=22050,
                                output=True
                            )
                            stream.write(audio_data)
                            stream.stop_stream()
                            stream.close()
                            spoken_via_piper = True
                    except Exception as exc:
                        print(f"[speech] Piper error: {exc}. Falling back to pyttsx3.")

            if not spoken_via_piper and engine is not None:
                try:
                    engine.say(text)
                    engine.runAndWait()
                except Exception as exc:
                    print(f"[speech] SAPI runtime error: {exc}")
                    # Try to recreate the engine instance on error
                    try:
                        engine = pyttsx3.init()
                        engine.setProperty("rate", 170)
                        engine.setProperty("volume", 1.0)
                        engine.say(text)
                        engine.runAndWait()
                    except Exception as retry_exc:
                        print(f"[speech] Failed to recover SAPI engine: {retry_exc}")
        finally:
            _speaking_event.clear()

        if done_event is not None:
            done_event.set()
        _speech_queue.task_done()

    # Cleanup PyAudio if it was initialized
    if p_audio is not None:
        try:
            p_audio.terminate()
        except Exception:
            pass


# Start the background TTS thread
_worker_thread = threading.Thread(target=_tts_worker, daemon=True)
_worker_thread.start()


def speak(text: str, block: bool = True) -> None:
    """
    Speak the given text aloud.
    If block=True (default), waits until the speech is finished.
    If block=False, queues the speech and returns immediately (non-blocking).
    """
    if not text.strip():
        return

    import re
    # Split into sentences to allow streaming-like playback latency
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    if not sentences:
        return

    if block:
        # Queue all sentences and wait for the last one to complete
        for idx, sentence in enumerate(sentences):
            is_last = (idx == len(sentences) - 1)
            done_event = threading.Event() if is_last else None
            _speech_queue.put((sentence, done_event))
            if is_last and done_event is not None:
                done_event.wait()
    else:
        # Non-blocking queue
        for sentence in sentences:
            _speech_queue.put((sentence, None))


def shutdown() -> None:
    """Stop the TTS background thread cleanly."""
    _speech_queue.put(None)



