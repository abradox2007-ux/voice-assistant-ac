"""server.py — lightweight Flask bridge between AC backend and the frontend UI."""

from __future__ import annotations

import time
from collections import deque
from threading import Lock
from flask import Flask, jsonify, send_from_directory

app = Flask(__name__, static_folder="frontend")

_lock = Lock()
_state: dict = {
    "phase": "idle",          # idle | waiting | listening | processing | error
    "message": "AC is offline.",
    "updated_at": time.time(),
}
_history: deque = deque(maxlen=50)   # most-recent 50 commands


# ── Public helpers (called from main.py) ─────────────────────────────────────

def set_status(phase: str, message: str) -> None:
    with _lock:
        _state["phase"] = phase
        _state["message"] = message
        _state["updated_at"] = time.time()


def get_status_phase() -> str:
    with _lock:
        return _state["phase"]



def add_history(command: str, response: str, ok: bool = True) -> None:
    with _lock:
        _history.appendleft({
            "command": command,
            "response": response,
            "ok": ok,
            "ts": time.strftime("%H:%M:%S"),
        })


# ── API routes ────────────────────────────────────────────────────────────────

@app.route("/api/status")
def api_status():
    with _lock:
        return jsonify({**_state})


@app.route("/api/history")
def api_history():
    with _lock:
        return jsonify(list(_history))


# ── Diary APIs ────────────────────────────────────────────────────────────────

@app.route("/api/diary", methods=["GET"])
def api_get_diary():
    from ac.handlers import diary
    return jsonify(diary.get_diary_entries())


@app.route("/api/diary/write", methods=["POST"])
def api_write_diary():
    from flask import request
    from ac.handlers import diary
    from ac.speech import speak
    data = request.json or {}
    text = data.get("text", "")
    
    # Speak command and response
    speak(f"Diary: {text}")
    response = diary.append_diary_entry(text)
    speak(response)
    
    return jsonify({"success": True, "message": response})


@app.route("/api/diary/overwrite", methods=["POST"])
def api_overwrite_diary():
    from flask import request
    from ac.handlers import diary
    from ac.speech import speak
    data = request.json or {}
    try:
        index = int(data.get("index", -1))
    except (ValueError, TypeError):
        index = -1
    text = data.get("text", "")
    
    # Speak command
    speak(f"Modify diary entry {index} to {text}")
    success = diary.update_entry(index, text)
    if success:
        speak("Diary entry updated successfully.")
    else:
        speak("Failed to update entry.")
        
    return jsonify({"success": success})


@app.route("/api/diary/delete", methods=["POST"])
def api_delete_diary():
    from flask import request
    from ac.handlers import diary
    from ac.speech import speak
    data = request.json or {}
    try:
        index = int(data.get("index", -1))
    except (ValueError, TypeError):
        index = -1
        
    # Speak command
    speak(f"Delete diary entry {index}")
    success = diary.delete_entry(index)
    if success:
        speak("Diary entry deleted successfully.")
    else:
        speak("Failed to delete entry.")
        
    return jsonify({"success": success})


@app.route("/api/status/reset", methods=["POST"])
def api_status_reset():
    set_status("idle", "AC is ready.")
    return jsonify({"success": True})


# ── Serve the frontend ────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("frontend", "index.html")


@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory("frontend", filename)


@app.after_request
def add_header(response):
    """Disable caching for all requests to prevent frontend cache issues."""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

