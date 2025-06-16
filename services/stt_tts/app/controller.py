# FastAPI controller to manage the stt_tts subprocess
from fastapi import FastAPI, Response
from subprocess import Popen
import signal
import os
import threading
import requests

app = FastAPI()

# COMMAND = ["python", "-m", "app.app"]
# Launch the full pipeline (vosk, whisper, tts, etc.)
PROCESS_CMD = ["python", "-m", "app.app"]
PROCESS_CWD = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
process = None
process_lock = threading.Lock()

@app.post("/tts/start")
def start_stt_tts():
    global process
    with process_lock:
        if process is not None and process.poll() is None:
            return {"status": "already running"}
        process = Popen(PROCESS_CMD, cwd=PROCESS_CWD)
        return {"status": "started"}

@app.post("/tts/stop")
def stop_stt_tts():
    global process
    with process_lock:
        if process is None or process.poll() is not None:
            return {"status": "not running"}
        process.terminate()
        try:
            process.wait(timeout=10)
        except Exception:
            process.kill()
        process = None
        return {"status": "stopped"}

@app.get("/tts/status")
def status():
    global process
    running = process is not None and process.poll() is None
    return {"running": running}

@app.post("/tts/speak")
def tts_speak(payload: dict):
    """
    Forwards the string to the subprocess's /speak endpoint if running.
    Expects JSON: {"text": "...", "gap": 0.5}
    """
    global process
    if process is None or process.poll() is not None:
        return {"status": "not running"}
    try:
        resp = requests.post("http://localhost:4210/tts/speak", json=payload, timeout=5)
        return resp.json()
    except Exception as e:
        return {"status": "error", "detail": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("controller:app", host="0.0.0.0", port=4208)
