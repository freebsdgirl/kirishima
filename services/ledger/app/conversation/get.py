"""
This module provides an API endpoint for retrieving all messages associated with a specific conversation
from the ledger database. It defines a FastAPI router with a single GET endpoint that fetches and returns
an ordered list of canonical conversation messages for a given conversation ID.

Functions:
    _open_conn() -> sqlite3.Connection:
        Opens a SQLite database connection with WAL journal mode enabled.

    get_conversation_messages(conversation_id: str) -> List[CanonicalConversationMessage]:
        API endpoint to retrieve all messages for a specific conversation, ordered by their internal ID.
"""

from app.config import BUFFER_DB
from shared.models.ledger import CanonicalConversationMessage

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

import sqlite3
from typing import List

from fastapi import APIRouter, Path

router = APIRouter()

TABLE = "conversation_messages"


def _open_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(BUFFER_DB, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


@router.get(
    "/ledger/conversation/{conversation_id}/messages",
    response_model=List[CanonicalConversationMessage],
)
def get_conversation_messages(
    conversation_id: str = Path(...),
) -> List[CanonicalConversationMessage]:
    """
    Retrieve all messages for a specific conversation from the database.

    Fetches messages associated with the given conversation ID, sorted by their internal ID.

    Args:
        conversation_id (str): Unique identifier for the conversation.

    Returns:
        List[CanonicalConversationMessage]: Ordered list of messages for the specified conversation.
    """

    logger.debug(f"Fetching messages for conversation {conversation_id}")

    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {TABLE} WHERE conversation_id = ? ORDER BY id", (conversation_id,))
        return [CanonicalConversationMessage(*row) for row in cur.fetchall()]
