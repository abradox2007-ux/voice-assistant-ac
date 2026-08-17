"""jarvis/listener.py — Microphone listener with always-on streaming, openWakeWord, and Silero VAD."""

from __future__ import annotations

import logging
import re
import queue
import threading
import time
import collections
from typing import Callable, Optional
import numpy as np
import speech_recognition as sr

from jarvis.vad import SileroVAD
from jarvis.utils import load_config
from jarvis.speech import is_speaking

logger = logging.getLogger(__name__)

WAKE_WORDS = ["hey jarvis", "hey, jarvis", "hey,jarvis", "jarvis"]


class Listener:
    def __init__(
        self,
        device_index: int | None = None,
        stt_engine: str = "google",
        whisper_model: str = "base",
        on_network_error: Callable[[], None] | None = None,
        on_mic_error: Callable[[], None] | None = None,
    ) -> None:
        self._recognizer = sr.Recognizer()
        self._recognizer.pause_threshold = 0.8
        self._recognizer.dynamic_energy_threshold = True
        self._ambient_adjusted = False
        self._device_index = device_index
        self._stt_engine = stt_engine.lower()
        self._whisper_model = whisper_model
        self._on_network_error = on_network_error or (lambda: None)
        self._on_mic_error = on_mic_error or (lambda: None)

        self._whisper_model_instance = None
        self._openwakeword_model = None
        self._vad = None

        # Load phase 2 config
        try:
            config = load_config()
        except Exception:
            config = {}

        self._wake_word_engine = config.get("wake_word_engine", "openwakeword")
        self._wake_word_model_name = config.get("wake_word_model", "hey_jarvis")
        self._wake_word_threshold = config.get("wake_word_threshold", 0.6)  # Default to 0.6 to prevent false triggers
        self._vad_threshold = config.get("vad_threshold", 0.35)  # Lower default threshold to be more sensitive to quiet voice
        self._vad_initial_timeout = config.get("vad_initial_timeout", 5.0)  # Time to wait for user to start speaking
        self._vad_model_path = config.get("vad_model_path", "bin/vad/silero_vad.onnx")

        # 1. Preload STT Whisper
        if self._stt_engine == "whisper":
            logger.info("Preloading faster-whisper model '%s'...", self._whisper_model)
            from faster_whisper import WhisperModel
            self._whisper_model_instance = WhisperModel(
                self._whisper_model,
                device="cpu",
                compute_type="int8"
            )
            logger.info("faster-whisper model preloaded.")

        # 2. Initialize openWakeWord
        if self._wake_word_engine == "openwakeword":
            logger.info("Initializing openWakeWord with model '%s'...", self._wake_word_model_name)
            try:
                from openwakeword.model import Model
                self._openwakeword_model = Model(
                    wakeword_models=[self._wake_word_model_name],
                    inference_framework="onnx"
                )
                logger.info("openWakeWord initialized.")
            except Exception as e:
                logger.error("Failed to load openWakeWord: %s", e)

        # 3. Initialize Silero VAD
        logger.info("Initializing Silero VAD from '%s'...", self._vad_model_path)
        try:
            self._vad = SileroVAD(self._vad_model_path)
            logger.info("Silero VAD initialized.")
        except Exception as e:
            logger.error("Failed to load Silero VAD: %s", e)

        # 4. Start the background always-on microphone streaming thread
        self._audio_queue: queue.Queue[bytes] = queue.Queue()
        self._running = True
        self._mic_thread = threading.Thread(target=self._mic_worker, daemon=True)
        self._mic_thread.start()

    # ── Static helpers ────────────────────────────────────────────────────────

    @staticmethod
    def contains_wake_word(text: str) -> bool:
        """Return True if *text* contains any wake-word variant."""
        t = text.lower().strip()
        for ww in WAKE_WORDS:
            if ww in t:
                return True
        # Fuzzy: "hey" followed by "ac" within 2 tokens
        tokens = re.split(r"\s+", t)
        for i, tok in enumerate(tokens):
            if tok in ("hey", "hay", "hi") and i + 1 < len(tokens):
                nxt = tokens[i + 1].replace(",", "").replace(".", "")
                if nxt in ("ac", "a.c", "a-c"):
                    return True
        return False

    @staticmethod
    def extract_command_from_wake(text: str) -> str:
        """Strip the wake word prefix and return the remainder."""
        t = text.lower().strip()
        for ww in WAKE_WORDS:
            if ww in t:
                idx = t.index(ww) + len(ww)
                return t[idx:].lstrip(", ").strip()
        # Fuzzy strip
        tokens = re.split(r"\s+", t)
        for i, tok in enumerate(tokens):
            if tok in ("hey", "hay", "hi") and i + 1 < len(tokens):
                nxt = tokens[i + 1].replace(",", "")
                if nxt in ("ac", "a.c", "a-c"):
                    return " ".join(tokens[i + 2:]).strip()
        return t

    # ── Streaming Microphone Worker ───────────────────────────────────────────

    def _mic_worker(self) -> None:
        """Background thread that reads raw audio frames from the mic continuously."""
        import pyaudio
        
        p = pyaudio.PyAudio()
        stream = None
        try:
            # We record at 16000Hz, Mono, 16-bit PCM (standard for VAD, wake word, STT)
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                input_device_index=self._device_index,
                frames_per_buffer=1024
            )
        except Exception as e:
            logger.error("Failed to open PyAudio mic stream: %s", e)
            self._on_mic_error()
            p.terminate()
            return

        logger.info("Microphone stream opened successfully.")
        while self._running:
            try:
                # Read 1024 samples (64ms of audio)
                data = stream.read(1024, exception_on_overflow=False)
                if data:
                    # Only queue audio frames if the assistant is not currently speaking
                    if not is_speaking():
                        self._audio_queue.put(data)
            except Exception as e:
                logger.warning("Error reading audio frame: %s", e)
                time.sleep(0.1)

        if stream:
            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass
        p.terminate()
        logger.info("Microphone stream closed.")

    # ── VAD Capturing State Machine ───────────────────────────────────────────

    def _capture_speech_with_vad(
        self,
        initial_audio: bytes,
        max_duration: float = 12.0
    ) -> sr.AudioData | None:
        """
        Record audio chunks from the queue using Silero VAD until speech ends.
        """
        accumulated_frames = [initial_audio] if initial_audio else []
        
        if self._vad is not None:
            self._vad.reset()
        
        speech_started = False
        silence_start_time = None
        start_time = time.time()

        # Run VAD on initial_audio to see if speech has already started
        if initial_audio and self._vad is not None:
            initial_samples = np.frombuffer(initial_audio, dtype=np.int16).astype(np.float32) / 32768.0
            for i in range(0, len(initial_samples), 512):
                if i + 512 <= len(initial_samples):
                    if self._vad.is_speech(initial_samples[i : i + 512], threshold=self._vad_threshold):
                        speech_started = True

        while self._running:
            if time.time() - start_time > max_duration:
                logger.debug("Reached max command duration limit.")
                break
                
            try:
                data = self._audio_queue.get(timeout=0.5)
            except queue.Empty:
                break
                
            accumulated_frames.append(data)
            
            # Check VAD on the new chunk
            if self._vad is not None:
                chunk = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
                
                # Split 1024 samples into two 512 VAD chunks sequentially to prevent state corruption
                prob1 = self._vad.get_speech_probability(chunk[:512])
                prob2 = self._vad.get_speech_probability(chunk[512:])
                is_speech_chunk = (prob1 >= self._vad_threshold) or (prob2 >= self._vad_threshold)
                
                logger.debug(
                    "VAD probabilities: chunk1=%.3f, chunk2=%.3f (threshold=%.3f, speech_started=%s)",
                    prob1, prob2, self._vad_threshold, speech_started
                )
                
                if is_speech_chunk:
                    if not speech_started:
                        logger.info("Speech started.")
                        speech_started = True
                    silence_start_time = None
                else:
                    if speech_started:
                        if silence_start_time is None:
                            silence_start_time = time.time()
                        elif time.time() - silence_start_time > 1.2:
                            logger.info("Speech ended (silence timeout).")
                            break
                    else:
                        # Cutoff if no speech detected at all within first self._vad_initial_timeout seconds
                        if time.time() - start_time > self._vad_initial_timeout:
                            logger.info("No speech detected (initial VAD timeout).")
                            break
            else:
                # If VAD failed to load, fall back to simple time limit
                if time.time() - start_time > 4.0:
                    speech_started = True  # Fallback to transcribe anyway
                    break

        if self._vad is not None and not speech_started:
            logger.info("No speech detected by VAD. Skipping transcription to prevent hallucination.")
            return None

        raw_wav = b"".join(accumulated_frames)
        return sr.AudioData(raw_wav, 16000, 2)

    def _transcribe(self, audio: sr.AudioData | None) -> str | None:
        if audio is None:
            return None
        try:
            if self._stt_engine == "whisper" and self._whisper_model_instance is not None:
                import io
                wav_data = io.BytesIO(audio.get_wav_data(convert_rate=16000, convert_width=2))
                segments, info = self._whisper_model_instance.transcribe(
                    wav_data,
                    beam_size=3,
                    language="en",
                    condition_on_previous_text=False
                )
                text_segments = []
                for segment in segments:
                    if segment.no_speech_prob < 0.6:
                        text_segments.append(segment.text)
                text = "".join(text_segments).strip()

                # Filter out standard Whisper hallucinations on low confidence / silent audio
                if text:
                    cleaned_text = text.lower().strip().rstrip(".!?")
                    hallucinations = {
                        "thank you", "thank you for watching", "you", 
                        "please subscribe", "subscribe", "bye", "watching"
                    }
                    if cleaned_text in hallucinations:
                        logger.info("Filtered out Whisper hallucination: '%s'", text)
                        return None

                return text if text else None
            else:
                # Transcribe in Indian English (optimized for local accents)
                return self._recognizer.recognize_google(audio, language="en-IN")
        except sr.UnknownValueError:
            return None
        except sr.RequestError:
            self._on_network_error()
            return None

    # ── Public interface ──────────────────────────────────────────────────────

    def wait_for_wake_word(self) -> tuple[str, Optional[str]]:
        """
        Block until the wake word is detected.
        Returns (full_transcript, inline_command_or_None).
        """
        # Allow any physical speaker output to finish playing and settle in the room
        time.sleep(0.8)

        # Clear queue of stale audio
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

        if self._vad is not None:
            self._vad.reset()

        # Rolling history buffer (1.5 seconds) to catch inline commands
        # 1.5s = ~24 chunks of 1024 samples at 16kHz
        history_buffer = collections.deque(maxlen=24)
        wakeword_accumulator = np.array([], dtype=np.int16)

        logger.info("Waiting for wake word...")

        while self._running:
            try:
                data = self._audio_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            history_buffer.append(data)

            # Feed openWakeWord
            if self._openwakeword_model is not None:
                chunk = np.frombuffer(data, dtype=np.int16)
                wakeword_accumulator = np.concatenate([wakeword_accumulator, chunk])

                while len(wakeword_accumulator) >= 1280:
                    predict_chunk = wakeword_accumulator[:1280]
                    wakeword_accumulator = wakeword_accumulator[1280:]

                    predictions = self._openwakeword_model.predict(predict_chunk)
                    score = predictions.get(self._wake_word_model_name, 0.0)

                    # Trigger threshold
                    if score > self._wake_word_threshold:
                        logger.info("Wake word '%s' detected! Score: %.2f (threshold: %.2f)", self._wake_word_model_name, score, self._wake_word_threshold)

                        # Collect history buffer raw bytes
                        pre_trigger_audio = b"".join(list(history_buffer))

                        # Check if user continued speaking in the next 500ms
                        speech_detected = False
                        check_chunks = []
                        for _ in range(8):  # 8 chunks of 64ms = ~512ms
                            try:
                                chk = self._audio_queue.get(timeout=0.6)
                                check_chunks.append(chk)
                                
                                if self._vad is not None:
                                    float_chunk = np.frombuffer(chk, dtype=np.int16).astype(np.float32) / 32768.0
                                    prob1 = self._vad.get_speech_probability(float_chunk[:512])
                                    prob2 = self._vad.get_speech_probability(float_chunk[512:])
                                    logger.debug(
                                        "Wake check VAD probabilities: chunk1=%.3f, chunk2=%.3f (threshold=%.3f)",
                                        prob1, prob2, self._vad_threshold
                                    )
                                    if (prob1 >= self._vad_threshold) or (prob2 >= self._vad_threshold):
                                        speech_detected = True
                            except queue.Empty:
                                break

                        if speech_detected:
                            logger.info("Inline command detected (speech continued).")
                            audio_data = self._capture_speech_with_vad(
                                pre_trigger_audio + b"".join(check_chunks)
                            )
                            text = self._transcribe(audio_data)
                            if text:
                                # We need to check if wake word needs to be stripped
                                # Using jarvis as fallback wake word strip
                                stripped = text
                                for term in ["jarvis", "hey jarvis", "alexa", "hey ac"]:
                                    if term in stripped.lower():
                                        idx = stripped.lower().index(term) + len(term)
                                        stripped = stripped[idx:].lstrip(", ").strip()
                                        break
                                return text, stripped if stripped else None
                        return "", None
            else:
                # Fallback if openwakeword model is not available: capture chunk and check with STT
                audio_data = self._capture_speech_with_vad(b"", max_duration=4.0)
                if audio_data is not None:
                    text = self._transcribe(audio_data)
                    if text and self.contains_wake_word(text):
                        cmd = self.extract_command_from_wake(text)
                        return text, cmd if cmd else None
                time.sleep(0.1)

    def capture_command(
        self,
        inline_command: str | None = None,
        timeout: int = 15,
    ) -> str | None:
        """
        Capture and return one spoken command (or return *inline_command* immediately).
        Returns None if nothing is heard.
        """
        if inline_command:
            return inline_command

        # Clear queue of stale audio
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

        logger.info("Listening for command...")
        audio = self._capture_speech_with_vad(b"", max_duration=float(timeout))
        return self._transcribe(audio)

    def close(self) -> None:
        """Stop the background mic streaming thread cleanly."""
        self._running = False
        if self._mic_thread.is_alive():
            self._mic_thread.join(timeout=2.0)
