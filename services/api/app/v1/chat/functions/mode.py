import api.config

import requests

from log_config import get_logger

logger = get_logger(__name__)


def change_mode(mode_name):
    """
    Change the current mode of the application.
    
    Args:
        mode_name (str): The name of the mode to change.
        mode_toggle (str): Toggle switch for the mode ('on' or 'off').
    
    Sets the global MODE configuration and logs the current mode.
    Supports 'nsfw' mode, defaulting to 'default' for unrecognized modes.
    arguments are passed as lower case variables.
    """
    match mode_name:
        case 'nsfw':
            requests.post(f"{api.config.BRAIN_API_URL}/status/mode/nsfw")
        case 'work':
            requests.post(f"{api.config.BRAIN_API_URL}/status/mode/work")
        case _:
            requests.post(f"{api.config.BRAIN_API_URL}/status/mode/default")

    logger.info(f"🕹️ MODE -> {mode_name}")


def get_mode() -> str:
    response = requests.get(f"{api.config.BRAIN_API_URL}/status/mode")
    mode = response.json()["message"]
    return mode
