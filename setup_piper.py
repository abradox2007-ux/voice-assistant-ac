import os
import sys
import zipfile
import urllib.request
import shutil
import subprocess
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent
BIN_DIR = BASE_DIR / "bin"
PIPER_DIR = BIN_DIR / "piper"
ZIP_PATH = BIN_DIR / "piper_windows_amd64.zip"

PIPER_ZIP_URL = "https://github.com/rhasspy/piper/releases/download/2023.11.14-2/piper_windows_amd64.zip"
MODEL_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
CONFIG_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

def download_file(url: str, dest: Path):
    print(f"Downloading {url}...")
    headers = {"User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, headers=headers)
    
    with urllib.request.urlopen(req) as response, open(dest, "wb") as out_file:
        length = response.getheader("content-length")
        if length:
            total_size = int(length)
            downloaded = 0
            block_size = 1024 * 64
            while True:
                block = response.read(block_size)
                if not block:
                    break
                out_file.write(block)
                downloaded += len(block)
                percent = int(downloaded * 100 / total_size)
                # print progress every 10%
                if percent % 10 == 0:
                    sys.stdout.write(f"\rProgress: {percent}% ({downloaded // (1024*1024)}MB / {total_size // (1024*1024)}MB)")
                    sys.stdout.flush()
            print()
        else:
            out_file.write(response.read())

def setup_piper():
    BIN_DIR.mkdir(exist_ok=True)
    
    # 1. Download Piper Zip
    if not ZIP_PATH.exists():
        download_file(PIPER_ZIP_URL, ZIP_PATH)
    else:
        print("Piper zip already downloaded.")
        
    # 2. Extract Piper Zip
    if not PIPER_DIR.exists():
        print(f"Extracting zip to {BIN_DIR}...")
        
        # Clean up any failed previous extraction attempts
        temp_extract = BIN_DIR / "temp_extract"
        if temp_extract.exists():
            try:
                shutil.rmtree(temp_extract)
            except Exception:
                pass
                
        with zipfile.ZipFile(ZIP_PATH, "r") as zip_ref:
            zip_ref.extractall(BIN_DIR)
            
        print("Piper extracted successfully.")
    else:
        print("Piper directory already exists.")

    # 3. Download Voice Model
    model_path = PIPER_DIR / "en_US-lessac-medium.onnx"
    config_path = PIPER_DIR / "en_US-lessac-medium.onnx.json"
    
    if not model_path.exists():
        download_file(MODEL_URL, model_path)
    else:
        print("Voice model (.onnx) already exists.")
        
    if not config_path.exists():
        download_file(CONFIG_URL, config_path)
    else:
        print("Voice config (.json) already exists.")
        
    # 4. Test execution
    piper_exe = PIPER_DIR / "piper.exe"
    if not piper_exe.exists():
        print("[Error] piper.exe not found in extracted files!")
        sys.exit(1)
        
    print("\nRunning quick test of piper.exe...")
    try:
        command = [
            str(piper_exe),
            "--model", str(model_path),
            "--output-raw"
        ]
        test_text = "Test."
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        audio, err = process.communicate(input=test_text.encode("utf-8"))
        if process.returncode == 0 and len(audio) > 0:
            print("[Success] piper.exe generated audio bytes successfully!")
        else:
            print(f"[Error] piper.exe test failed. Return code: {process.returncode}, Error: {err.decode('utf-8', errors='ignore')}")
            sys.exit(1)
    except Exception as exc:
        print(f"[Error] Failed to run test of piper.exe: {exc}")
        sys.exit(1)

if __name__ == "__main__":
    setup_piper()
