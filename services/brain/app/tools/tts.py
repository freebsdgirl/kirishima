import httpx
import json
import os

with open('/app/config/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]

def tts(action: str):
    """
    Handle TTS actions by forwarding the request to the TTS service.
    
    Args:
        action (str): The action to perform, such as 'start', 'stop', or 'status'.
    
    Returns:
        dict: A dictionary containing the status of the action.
    
    Raises:
        HTTPException: If the action is not recognized or if there is an error communicating with the TTS service.
    """
    try:
        tts_port = os.getenv("TTS_PORT", 4208)

        url = f"http://host.docker.internal:{tts_port}/tts/{action}"
        with httpx.Client(timeout=TIMEOUT) as client:
            response = client.post(url)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {"status": "error", "error": str(e)}