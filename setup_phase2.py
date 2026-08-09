import os
import sys
import subprocess
import urllib.request
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent
BIN_DIR = BASE_DIR / "bin"
VAD_DIR = BIN_DIR / "vad"
VAD_MODEL_PATH = VAD_DIR / "silero_vad.onnx"

VAD_URL = "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/silero_vad.onnx"

def download_file(url: str, dest: Path):
    print(f"Downloading {url} to {dest}...")
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    
    with urllib.request.urlopen(req) as response, open(dest, "wb") as out_file:
        out_file.write(response.read())
    print("Download complete.")

def setup():
    # 1. Install openwakeword
    print("Installing openwakeword in the virtual environment...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "openwakeword"],
            check=True
        )
        print("[Success] openwakeword installed successfully.")
    except subprocess.CalledProcessError as err:
        print(f"[Error] Failed to install openwakeword: {err}")
        sys.exit(1)
        
    # 2. Download Silero VAD model
    VAD_DIR.mkdir(parents=True, exist_ok=True)
    if not VAD_MODEL_PATH.exists():
        download_file(VAD_URL, VAD_MODEL_PATH)
    else:
        print("Silero VAD ONNX model already exists.")
        
    # 3. Test openwakeword initialization
    print("\nVerifying openwakeword model initialization...")
    try:
        from openwakeword.utils import download_models
        print("Downloading built-in openwakeword models (this may take a minute)...")
        download_models()

        from openwakeword.model import Model
        # Initialize with 'hey_jarvis' built-in model
        print("Initializing openwakeword with 'hey_jarvis' model...")
        model = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")
        print("[Success] openwakeword initialized successfully!")
    except Exception as exc:
        print(f"[Error] Failed to initialize openwakeword: {exc}")
        sys.exit(1)
        
    # 4. Test Silero VAD initialization via ONNX Runtime
    print("\nVerifying Silero VAD ONNX initialization...")
    try:
        import onnxruntime as ort
        print(f"Loading ONNX model from {VAD_MODEL_PATH}...")
        session = ort.InferenceSession(str(VAD_MODEL_PATH), providers=["CPUExecutionProvider"])
        print("[Success] Silero VAD ONNX Session initialized successfully!")
    except Exception as exc:
        print(f"[Error] Failed to initialize Silero VAD ONNX Session: {exc}")
        sys.exit(1)

if __name__ == "__main__":
    setup()
