"""Voice Assistant AC — entry point with frontend server integration."""

from __future__ import annotations

import sys
import time
import threading

from ac.listener import Listener
from ac.router import CommandRouter
from ac.speech import shutdown as shutdown_speech
from ac.speech import speak
from ac.utils import load_config, setup_logging
from server import app as flask_app, set_status, add_history


LISTEN_TIMEOUT = 15  # seconds to wait for a command before giving up


def run_flask():
    """Run Flask in a background thread."""
    flask_app.run(host="0.0.0.0", port=5050, debug=False, use_reloader=False)


def main() -> None:
    logger = setup_logging()
    logger.info("Starting Voice Assistant AC")

    try:
        config = load_config()
    except Exception as exc:
        print(f"Failed to load config.json: {exc}")
        sys.exit(1)

    # Start Flask frontend server in background
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Frontend server started at http://localhost:5050")                 ##hoooooooooooo
                                                                                    ##ha ha ha bankai zenponzakura kageyoshi

    router = CommandRouter(config)
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
        on_network_error=on_network_error,
        on_mic_error=on_mic_error,
    )

    greeting = "AC is ready. Say hey AC followed by your command."
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
                set_status("waiting", "Waiting for wake word... say \"Hey AC\"")
                _, inline_command = listener.wait_for_wake_word()

                speak("Yes?")
                set_status("listening", "Listening... speak your command now")

                # ── Phase 2: Capture command with 15s timeout ────────────
                command = None
                deadline = time.time() + LISTEN_TIMEOUT

                while time.time() < deadline:
                    remaining = max(0, int(deadline - time.time()))
                    set_status(
                        "listening",
                        f"Listening... ({remaining}s left)",
                    )
                    command = listener.capture_command(
                        inline_command=inline_command,
                        timeout=min(3, max(1, remaining)),   # short polling chunks
                    )
                    if command:
                        break
                    inline_command = None  # only use inline once

                # ── Phase 3: Handle timeout ──────────────────────────────
                if not command:
                    timeout_msg = "Couldn't understand command. Tell again."
                    speak(timeout_msg)
                    set_status("waiting", timeout_msg)
                    add_history("(timeout)", timeout_msg, ok=False)
                    time.sleep(0.5)
                    restart_msg = 'Tell your command by saying "Hey AC" and your command.'
                    speak(restart_msg)
                    set_status("idle", restart_msg)
                    continue

                # ── Phase 4: Route the command ───────────────────────────
                set_status("processing", f'Processing: "{command}"')
                speak(command)
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
