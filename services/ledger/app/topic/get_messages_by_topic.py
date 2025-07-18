"""
This module provides an API endpoint and helper function for retrieving user messages associated with a specific topic.
Functions:
    _get_topic_messages(topic_id: str) -> List[CanonicalUserMessage]:
        Fetches and returns all user messages for a given topic ID from the database, ordered by message ID.
        Parses JSON fields ('tool_calls' and 'function_call') as needed, constructs CanonicalUserMessage objects,
        and filters out messages with the role 'tool' and assistant messages with empty content.
    get_messages_by_topic(topic_id: str) -> List[CanonicalUserMessage]:
        FastAPI route handler that checks if the specified topic exists, then returns all user messages for that topic.
        Raises HTTPException with 404 status if the topic does not exist.
Dependencies:
    - FastAPI for API routing and exception handling.
    - Shared models for CanonicalUserMessage.
    - Utility functions for database connection and topic existence checking.
"""

from app.util import _open_conn
from app.topic.util import topic_exists
from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")
from fastapi import APIRouter, HTTPException, status
from typing import List
import json
from shared.models.ledger import CanonicalUserMessage

router = APIRouter()


def _get_topic_messages(topic_id: str) -> List[CanonicalUserMessage]:
    """
    Helper function to get messages for a specific topic.
    """
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_messages WHERE topic_id = ? ORDER BY id", (topic_id,))
        columns = [col[0] for col in cur.description]
        raw_messages = [dict(zip(columns, row)) for row in cur.fetchall()]
        
        # Parse JSON fields if needed
        for msg in raw_messages:
            if msg.get("tool_calls"):
                try:
                    msg["tool_calls"] = json.loads(msg["tool_calls"])
                except Exception:
                    msg["tool_calls"] = None
            if msg.get("function_call"):
                try:
                    msg["function_call"] = json.loads(msg["function_call"])
                except Exception:
                    msg["function_call"] = None
        
        messages = [CanonicalUserMessage(**msg) for msg in raw_messages]
        # Filter out tool messages and assistant messages with empty content
        messages = [
            msg for msg in messages
            if not (
                getattr(msg, 'role', None) == 'tool' or
                (getattr(msg, 'role', None) == 'assistant' and not getattr(msg, 'content', None))
            )
        ]
        return messages


@router.get("/topics/{topic_id}/messages", response_model=List[CanonicalUserMessage])
def get_messages_by_topic(topic_id: str) -> List[CanonicalUserMessage]:
    """
    Retrieve all user messages associated with a given topic ID.

    This function checks if the specified topic exists, then queries the database for all messages
    related to the topic, ordered by their ID. It parses the 'tool_calls' field from JSON if necessary,
    constructs CanonicalUserMessage objects, and filters out messages with the role 'tool' as well as
    assistant messages with empty content.

    Args:
        topic_id (str): The unique identifier of the topic.

    Returns:
        List[CanonicalUserMessage]: A list of user messages for the topic, excluding tool messages and
        assistant messages with empty content.

    Raises:
        HTTPException: If the topic does not exist (404 Not Found).
    """
    if not topic_exists(topic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")
    return _get_topic_messages(topic_id)

