"""
LISTENER PATCH — ac/listener.py
================================
The new main.py passes `timeout=` to `capture_command()`.
Make sure your existing capture_command() accepts (and uses) it.

Minimal change — add the `timeout` kwarg with a default:

    # BEFORE
    def capture_command(self, inline_command: str | None = None) -> str | None:
        ...

    # AFTER
    def capture_command(
        self,
        inline_command: str | None = None,
        timeout: int = 10,
    ) -> str | None:
        ...
        # Pass timeout to the recognizer:
        audio = self._recognizer.listen(source, timeout=timeout, phrase_time_limit=timeout)
        ...

The main loop already handles the outer 10-second deadline by calling
capture_command() in short (3-second) polling chunks, so even a partial
recognition is returned immediately and the loop breaks early.
"""
