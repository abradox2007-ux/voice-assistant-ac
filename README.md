# 🎙️ Jarvis — Voice Assistant

An intelligent, local-first AI Voice Assistant with real-time wake word detection, Voice Activity Detection (VAD), fast speech-to-text, offline text-to-speech, Gemini AI intelligence, and a dynamic web dashboard.

---

## ✨ Features

- **Wake Word & VAD Detection**: Hands-free activation powered by [openWakeWord](https://github.com/dscripka/openWakeWord) and Silero VAD (via ONNX Runtime).
- **Fast & Accurate STT**: Uses `faster-whisper` for local offline transcription with Google Speech Recognition fallback.
- **Offline / Low-Latency TTS**: Asynchronous speech engine with `pyttsx3` and support for Piper local neural TTS.
- **AI Intelligence**: Integrated with Google Gemini AI (`google-genai`) for smart conversational answers.
- **Rich Command Handlers**:
  - 🌐 **Web & Media**: Open URLs, search Google, play YouTube videos directly.
  - 🚀 **App Launcher**: Launch desktop apps (Chrome, Notepad, Calculator, VS Code, etc.).
  - 📖 **Voice Diary**: Record thoughts and voice notes saved locally with timestamps.
  - 🕒 **Time & Weather**: Real-time time, date, and weather updates.
  - 📁 **File Search**: Search files across Desktop, Documents, and configured paths.
- **Interactive Web UI**: Modern web dashboard on `http://localhost:5050` with real-time status, audio wave visualizer, command history, and diary log viewer.

---

## 📁 Project Structure

```text
AC_VoiceAssistant/
├── config.example.json      # Template configuration file
├── config.json              # Your private config (API keys, aliases)
├── main.py                  # Main entry point for voice assistant & Web UI
├── server.py                # Flask backend server for web dashboard
├── requirements.txt         # Python dependencies
├── setup_piper.py           # Setup script for Piper local neural TTS (optional)
├── setup_phase2.py          # Setup helper for offline models
├── frontend/                # Web Dashboard UI (HTML, CSS, JS)
├── jarvis/                  # Core assistant package
│   ├── listener.py          # Audio capture, wake word, VAD & STT
│   ├── router.py            # Command parsing and intent routing
│   ├── speech.py            # TTS speech engine and queue
│   ├── vad.py               # Silero Voice Activity Detector
│   ├── utils.py             # Config loader and logger utilities
│   └── handlers/            # Modular feature handlers
│       ├── ai.py            # Gemini AI handler
│       ├── apps.py          # Application launcher
│       ├── diary.py         # Voice diary manager
│       ├── files.py         # Local file search
│       ├── info.py          # Weather, time, and system info
│       └── urls.py          # Web and YouTube handler
└── data/                    # Local storage (diary notes, cached models)
```

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.10+** (64-bit recommended)
- Working Microphone & Speakers / Headphones
- (Windows) Visual C++ Redistributable (if required by ONNX runtime / PyAudio)

### 2. Clone the Repository
```bash
git clone https://github.com/abradox2007-ux/Jarvis.git
cd Jarvis
```

### 3. Create & Activate Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
*(If script execution is disabled in PowerShell, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first)*

**On Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate.bat
```

**On Linux / macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 4. Install Dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

> **Note for PyAudio on Windows:** If `pyaudio` fails to compile via pip, install the prebuilt wheel using `pip install pipwin && pipwin install pyaudio` or download the appropriate `.whl` from Christoph Gohlke's unofficial binaries.

### 5. Configuration Setup

Copy `config.example.json` to `config.json`:
```bash
cp config.example.json config.json
```

Edit `config.json` with your custom settings:
```json
{
  "gemini_api_key": "YOUR_GEMINI_API_KEY_HERE",
  "search_paths": [
    "~/Desktop",
    "~/Documents",
    "./data"
  ],
  "url_aliases": {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "github": "https://github.com",
    "gmail": "https://mail.google.com"
  },
  "app_aliases": {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "chrome": "chrome",
    "explorer": "explorer.exe"
  },
  "weather_city": "Chennai",
  "weather_country": "IN"
}
```

- Get your free Gemini API Key at: [Google AI Studio](https://aistudio.google.com/)

---

## 🏃 Running Jarvis

With your virtual environment activated:

```bash
python main.py
```

1. Jarvis will initialize the audio devices and speech engines.
2. The web interface will automatically open at `http://localhost:5050`.
3. Say `"Hey Jarvis"` to wake the assistant, then speak your command!

---

## 🗣️ Example Voice Commands

| Category | Example Voice Commands |
| :--- | :--- |
| **Wake Word** | *"Hey Jarvis"* |
| **Web & Media** | *"Open YouTube"*, *"Play Interstellar soundtrack on YouTube"*, *"Search Google for Python tutorials"* |
| **Applications** | *"Open Notepad"*, *"Launch Chrome"*, *"Open Calculator"* |
| **Diary / Notes** | *"Write a diary entry: completed milestone one today"*, *"Read my last diary entry"* |
| **Information** | *"What's the weather today?"*, *"What time is it?"*, *"What date is today?"* |
| **AI Questions** | *"Explain quantum computing in simple terms"*, *"Write a short poem about coding"* |
| **Exit** | *"Stop"*, *"Exit"*, *"Goodbye Jarvis"* |

---

## 🧪 Testing

Run test suite:
```bash
pytest test_jarvis.py
```
or
```bash
python -m unittest test_jarvis.py
```

---

## 📄 License

This project is licensed under the MIT License — see the repository for details.
