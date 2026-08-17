"""Voice Assistant Jarvis — entry point with frontend server integration."""

from __future__ import annotations

import sys
import time
import threading
import webbrowser

from jarvis.listener import Listener
from jarvis.router import CommandRouter
from jarvis.speech import shutdown as shutdown_speech
from jarvis.speech import speak
from jarvis.utils import load_config, setup_logging
from server import app as flask_app, set_status, add_history, set_router


LISTEN_TIMEOUT = 15  # seconds to wait for a command before giving up


def run_flask():
    """Run Flask in a background thread."""
    flask_app.run(host="0.0.0.0", port=5050, debug=False, use_reloader=False)


def main() -> None:
    logger = setup_logging()
    logger.info("Starting Voice Assistant Jarvis")

    try:
        config = load_config()
    except Exception as exc:
        print(f"Failed to load config.json: {exc}")
        sys.exit(1)

    router = CommandRouter(config)
    set_router(router)

    # Start Flask frontend server in background
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Frontend server started at http://localhost:5050")

    # Automatically open the localhost frontend in the default browser.
    # We use a brief delay (0.5 seconds) to ensure the server starts up first.
    try:
        threading.Timer(0.5, lambda: webbrowser.open("http://localhost:5050")).start()
    except Exception as exc:
        logger.warning("Could not open web browser automatically: %s", exc)
    network_error_spoken = False
    mic_error_spoken = False

    def on_network_error() -> None:
        nonlocal network_error_spoken
        if not network_error_spoken:
            msg = "I need an internet connection for speech recognition."
            speak(msg)
            set_status("error", msg)
            network_error_spoken = True

    def on_mic_error() -> None:
        nonlocal mic_error_spoken
        if not mic_error_spoken:
            msg = "Microphone not available. Please check your settings."
            speak(msg)
            set_status("error", msg)
            mic_error_spoken = True

    listener = Listener(
        device_index=config.get("mic_index"),
        stt_engine=config.get("stt_engine", "google"),
        whisper_model=config.get("whisper_model", "base"),
        on_network_error=on_network_error,
        on_mic_error=on_mic_error,
    )

    greeting = "Jarvis is ready. Say Hey Jarvis followed by your command."
    speak(greeting)
    set_status("idle", greeting)

    try:
        while True:
            try:
                # ── Phase 0: Wait if in manual diary mode ────────────────
                from server import get_status_phase
                while get_status_phase() == "diary_manual":
                    time.sleep(0.2)

                # ── Phase 1: Wait for wake word ──────────────────────────
                set_status("waiting", "Waiting for wake word... say \"Hey Jarvis\"")
                _, inline_command = listener.wait_for_wake_word()

                speak("Yes?")
                set_status("listening", "Listening... speak your command now")

                # ── Phase 2: Capture command with 15s timeout ────────────
                if inline_command:
                    command = inline_command
                else:
                    set_status("listening", "Listening... speak your command now")
                    command = listener.capture_command(timeout=LISTEN_TIMEOUT)

                # ── Phase 3: Handle timeout ──────────────────────────────
                if not command:
                    timeout_msg = "Couldn't understand command. Tell again."
                    speak(timeout_msg)
                    set_status("waiting", timeout_msg)
                    add_history("(timeout)", timeout_msg, ok=False)
                    time.sleep(0.5)
                    restart_msg = 'Tell your command by saying "Hey Jarvis" and your command.'
                    speak(restart_msg)
                    set_status("idle", restart_msg)
                    continue

                # ── Phase 4: Route the command ───────────────────────────
                set_status("processing", f'Processing: "{command}"')
                response = router.route(command)
                speak(response)
                add_history(command, response, ok=True)
                if response != "Opening manual diary panel.":
                    set_status("idle", f'Done: {response[:60]}{"…" if len(response) > 60 else ""}')

                network_error_spoken = False
                mic_error_spoken = False

            except KeyboardInterrupt:
                raise
            except Exception as exc:
                logger.exception("Unhandled error in main loop: %s", exc)
                err_msg = "Something went wrong. Try again."
                speak(err_msg)
                set_status("error", err_msg)
                time.sleep(0.5)

    except KeyboardInterrupt:
        logger.info("Shutting down on user interrupt.")
        speak("Goodbye.")
        set_status("idle", "AC is offline.")
    finally:
        shutdown_speech()


if __name__ == "__main__":
    main()
