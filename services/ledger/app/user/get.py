"""
This module provides an API endpoint for retrieving all messages associated with a specific user from the ledger database.

Endpoints:
- GET /ledger/user/{user_id}/messages: Returns a list of CanonicalUserMessage objects for the specified user, ordered by message ID.

Dependencies:
- Uses FastAPI for routing.
- Connects to a SQLite database specified by BUFFER_DB.
- Utilizes CanonicalUserMessage model for response serialization.
- Logging is configured via shared.log_config.get_logger.
"""

from app.config import BUFFER_DB
from shared.models.ledger import CanonicalUserMessage

from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

import sqlite3
from typing import List

from fastapi import APIRouter, Path, Body

router = APIRouter()


@router.get("/ledger/user/{user_id}/messages", response_model=List[CanonicalUserMessage])
def get_user_messages(user_id: str = Path(...)) -> List[CanonicalUserMessage]:
    """
    Retrieve all messages for a specific user from the ledger database.

    Fetches user messages ordered by their ID via a GET request.

    Args:
        user_id (str): The unique identifier of the user whose messages are to be retrieved.

    Returns:
        List[CanonicalUserMessage]: A list of canonical user messages associated with the specified user.
    """
    """Return the entire message list for a user (ordered by id)."""
    with sqlite3.connect(BUFFER_DB, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_messages WHERE user_id = ? ORDER BY id", (user_id,))
        return [CanonicalUserMessage(*row) for row in cur.fetchall()]

