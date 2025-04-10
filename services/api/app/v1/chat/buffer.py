import app.config

from shared.log_config import get_logger

logger = get_logger(__name__)

from pydantic import BaseModel
import requests
from datetime import datetime
from app.v1.chat.functions.mode import get_mode


class BufferMessage(BaseModel):
    """
    Represents a message entry for the rolling buffer database.
    
    Attributes:
        sender (str): The sender of the message.
        content (str): The content of the message.
        timestamp (str): The timestamp of when the message was sent.
        platform (str): The platform from which the message originated.
        mode (str): The mode or context of the message.
    """
    sender: str
    content: str
    timestamp: str
    platform: str
    mode: str


def add_to_buffer(message: str, sender: str, platform: str = "proxy", mode: str = "") -> None:
    """
    Add a message to the conversation buffer via an API call.
    
    Sends a buffer entry to the brain API with message details including sender, 
    content, timestamp, platform, and mode. Logs successful additions and 
    any failures during the buffer insertion process.
    
    Args:
        message (str): The content of the message to be buffered.
        sender (str): The sender of the message.
        platform (str, optional): The platform origin of the message. Defaults to "proxy".
        mode (str, optional): The mode or context of the message.
    """

    mode = get_mode()
    try:
        buffer_entry = BufferMessage(
            sender=sender,
            content=message,
            timestamp=datetime.utcnow().isoformat(),
            platform=platform,
            mode=mode
        )

        response = requests.post(
            f"{app.config.BRAIN_API_URL}/buffer/conversation",
            json=buffer_entry.dict()
        )

        if response.status_code != 200:
            logger.warning(f"Failed to insert buffer entry: {response.text}")

        logger.debug(f"Buffer entry added: {buffer_entry.json()}")

    except Exception as e:
        logger.error(f"Exception while sending buffer entry: {str(e)}")


def get_buffer_prompt() -> str:
    """
    Fetches conversation summaries from the brain API and constructs a single string prompt.
    
    The prompt is built with each line formatted as:
    <timestamp>: <summary>
    Lines are ordered from oldest to newest.
    
    Returns:
        A string containing the formatted summaries, or an empty string if an error occurs.
    """
    try:
        # Fetch summaries from the brain API endpoint.
        response = requests.get(f"{app.config.BRAIN_API_URL}/buffer/conversation")
        response.raise_for_status()
        summaries = response.json()  # Expected to be a list of dicts with keys "timestamp" and "summary"
        
        # Build the prompt string from the summaries.
        lines = []
        for item in summaries:
            line = f"{item['timestamp']}: {item['summary']}"
            lines.append(line)
        
        prompt_str = "\n".join(lines)
        return prompt_str
    
    except Exception as e:
        logger.error(f"Error fetching buffer conversation: {e}")
        return ""
