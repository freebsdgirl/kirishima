"""
This module provides an API endpoint for synchronizing conversation messages in a ledger system.

It defines a FastAPI router with a single POST endpoint:
    /ledger/conversation/{conversation_id}/sync

The endpoint receives a list of raw conversation messages and appends the latest message to a SQLite buffer.
It then returns the canonical list of conversation messages for the specified conversation, ordered by ID.

Modules and Classes:
- BUFFER_DB: Path to the SQLite database buffer.
- RawConversationMessage: Pydantic model representing a raw conversation message.
- CanonicalConversationMessage: Pydantic model representing a canonical conversation message.
- get_logger: Function to obtain a configured logger instance.

Endpoint:
- sync_conversation_buffer: Synchronizes and retrieves conversation messages for a given conversation ID.

Dependencies:
- FastAPI for API routing and request handling.
- SQLite3 for database operations.
- Pydantic models for request and response validation.
"""

from app.config import BUFFER_DB
from shared.models.ledger import RawConversationMessage, CanonicalConversationMessage

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

import sqlite3
from typing import List

from fastapi import APIRouter, Path, Body

router = APIRouter()


@router.post("/ledger/conversation/{conversation_id}/sync", response_model=List[CanonicalConversationMessage])
def sync_conversation_buffer(
    conversation_id: str = Path(..., description="Discord channel / thread identifier"),
    snapshot: List[RawConversationMessage] = Body(..., embed=True)
) -> List[CanonicalConversationMessage]:
    """
    Synchronize conversation messages for a specific conversation by appending the latest message to the buffer.

    Args:
        conversation_id: Unique identifier for the Discord channel or thread
        snapshot: List of raw conversation messages to be synchronized

    Returns:
        A list of canonical conversation messages for the specified conversation, ordered by ID
    """
    if not snapshot:
        return []

    last_msg = snapshot[-1]

    with sqlite3.connect(BUFFER_DB, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO conversation_messages (conversation_id, platform, role, content) VALUES (?, ?, ?, ?)",
            (conversation_id, last_msg.platform, last_msg.role, last_msg.content),
        )
        conn.commit()
        cur.execute(f"SELECT * FROM conversation_messages WHERE conversation_id = ? ORDER BY id", (conversation_id,))
        return [CanonicalConversationMessage(*row) for row in cur.fetchall()]
