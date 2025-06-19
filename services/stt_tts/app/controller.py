"""
Controller module for managing Text-to-Speech (TTS) and Speech-to-Text (STT) subprocesses via FastAPI.

This module provides a REST API for starting, stopping, and checking the status of TTS and STT services,
as well as forwarding TTS requests to a local backend and streaming audio responses in an OpenAI-compatible format.

Endpoints:
    - /tts/start: Start the TTS subprocess.
    - /tts/stop: Stop the TTS subprocess.
    - /tts/status: Check if the TTS subprocess is running.
    - /tts/speak: Forward TTS requests to the local TTS backend.
    - /v1/audio/speech: OpenAI-compatible TTS endpoint, streams audio from the backend.
    - /stt/start: Start the STT subprocess.
    - /stt/stop: Stop the STT subprocess.
    - /stt/status: Check if the STT subprocess is running.

Thread safety is ensured using locks for process management. Subprocesses are launched and terminated gracefully,
with fallback to forceful termination if needed. The module is intended to be run as a FastAPI application.

TODO: paths and variables should be in config.json, not hardcoded.
"""
import os
import requests

from subprocess import Popen
import threading

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

app = FastAPI()

# Launch the TTS and STT subprocesses
TTS_PROCESS_CMD = ["python", "tts_service.py"]
TTS_PROCESS_CWD = os.path.dirname(os.path.abspath(__file__))
TTS_PROCESS = None
TTS_LOCK = threading.Lock()

STT_PROCESS_CMD = ["python", "stt_service.py"]
STT_PROCESS_CWD = os.path.dirname(os.path.abspath(__file__))
STT_PROCESS = None
STT_LOCK = threading.Lock()


@app.post("/tts/start")
def start_tts():
    """
    Starts the Text-to-Speech (TTS) process if it is not already running.

    This endpoint checks if the TTS process is currently active. If it is not running,
    it starts the process using the specified command and working directory. If the process
    is already running, it returns a status indicating so.

    Returns:
        dict: A dictionary with the status of the TTS process, either "started" or "already running".
    """
    global TTS_PROCESS
    with TTS_LOCK:
        if TTS_PROCESS is not None and TTS_PROCESS.poll() is None:
            return {"status": "already running"}
        TTS_PROCESS = Popen(TTS_PROCESS_CMD, cwd=TTS_PROCESS_CWD)
        return {"status": "started"}


@app.post("/tts/stop")
def stop_tts():
    """
    Stops the currently running Text-to-Speech (TTS) process, if any.

    This function checks if a global TTS process is running. If it is, the process is terminated gracefully.
    If the process does not terminate within 10 seconds, it is forcefully killed. The function is thread-safe
    and uses a lock to prevent concurrent modifications.

    Returns:
        dict: A dictionary indicating the status of the TTS process. Possible values are:
            - {"status": "not running"}: No TTS process was running.
            - {"status": "stopped"}: The TTS process was successfully stopped.
    """
    global TTS_PROCESS
    with TTS_LOCK:
        if TTS_PROCESS is None or TTS_PROCESS.poll() is not None:
            return {"status": "not running"}
        TTS_PROCESS.terminate()
        try:
            TTS_PROCESS.wait(timeout=10)
        except Exception:
            TTS_PROCESS.kill()
        TTS_PROCESS = None
        return {"status": "stopped"}


@app.get("/tts/status")
def tts_status():
    """
    Check the status of the TTS (Text-to-Speech) process.

    Returns:
        dict: A dictionary with a single key 'running' indicating whether the TTS process is currently active.
    """
    global TTS_PROCESS
    running = TTS_PROCESS is not None and TTS_PROCESS.poll() is None
    return {"running": running}


@app.post("/stt/start")
def start_stt():
    """
    Starts the Speech-to-Text (STT) process if it is not already running.

    This function acquires a lock to ensure thread safety, checks if the STT process is already running,
    and if not, starts a new STT process using the specified command and working directory.

    Returns:
        dict: A dictionary indicating whether the STT process was started or was already running.
    """
    global STT_PROCESS
    with STT_LOCK:
        if STT_PROCESS is not None and STT_PROCESS.poll() is None:
            return {"status": "already running"}
        STT_PROCESS = Popen(STT_PROCESS_CMD, cwd=STT_PROCESS_CWD)
        return {"status": "started"}


@app.post("/stt/stop")
def stop_stt():
    """
    Stops the currently running Speech-to-Text (STT) process, if any.

    This function acquires a lock to ensure thread safety, checks if the STT process is running,
    and attempts to terminate it gracefully. If the process does not terminate within 10 seconds,
    it is forcefully killed. Updates the global STT_PROCESS variable to None after stopping.

    Returns:
        dict: A dictionary indicating the status of the STT process, either "not running" or "stopped".
    """
    global STT_PROCESS
    with STT_LOCK:
        if STT_PROCESS is None or STT_PROCESS.poll() is not None:
            return {"status": "not running"}
        STT_PROCESS.terminate()
        try:
            STT_PROCESS.wait(timeout=10)
        except Exception:
            STT_PROCESS.kill()
        STT_PROCESS = None
        return {"status": "stopped"}


@app.get("/stt/status")
def stt_status():
    """
    Check the status of the STT (Speech-to-Text) process.

    Returns:
        dict: A dictionary with a single key 'running' indicating whether the STT process is currently active.
    """
    global STT_PROCESS
    running = STT_PROCESS is not None and STT_PROCESS.poll() is None
    return {"running": running}


@app.post("/tts/speak")
def tts_speak(payload: dict):
    """
    Sends a text-to-speech (TTS) request to a local TTS service if the TTS process is running.

    Args:
        payload (dict): The JSON payload containing the data required for the TTS service.

    Returns:
        dict: A dictionary containing the response from the TTS service, or a status message if the TTS process is not running or an error occurs.
    """
    global TTS_PROCESS
    if TTS_PROCESS is None or TTS_PROCESS.poll() is not None:
        return {"status": "not running"}
    try:
        resp = requests.post("http://localhost:4210/tts/speak", json=payload, timeout=5)
        return resp.json()
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.post("/v1/audio/speech")
async def openai_compatible_tts(request: Request):
    """
    Handles OpenAI-compatible Text-to-Speech (TTS) requests by forwarding the incoming JSON payload
    to a local TTS backend and streaming the resulting audio response.

    Args:
        request (Request): The incoming HTTP request containing the TTS parameters in JSON format.

    Returns:
        StreamingResponse: Streams the audio data from the local TTS backend with appropriate headers,
            mimicking OpenAI's TTS API response.
        dict: An error response with status and detail if the request to the backend fails.
    """
    data = await request.json()
    # Forward the request to the local TTS backend
    try:
        resp = requests.post("http://localhost:4210/v1/audio/speak", json=data, timeout=30, stream=True)
        resp.raise_for_status()
        # Pass through the audio as a stream, mimicking OpenAI's response
        return StreamingResponse(
            resp.raw,
            media_type=resp.headers.get("content-type", "audio/mpeg"),
            headers={
                k: v for k, v in resp.headers.items() if k.lower().startswith("content-disposition")
            }
        )
    except Exception as e:
        return {"status": "error", "detail": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("controller:app", host="0.0.0.0", port=4208)
