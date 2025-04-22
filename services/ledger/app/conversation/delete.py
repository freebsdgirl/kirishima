"""
This module provides FastAPI endpoints for deleting conversation messages from the buffer database.

Endpoints:
- DELETE /ledger/conversation/{conversation_id}/before/{message_id}:
    Deletes all messages in a conversation up to and including a specified message ID.
- DELETE /ledger/conversation/{conversation_id}:
    Deletes all messages for a specific conversation.

Utilities:
- _open_conn(): Opens a SQLite connection to the buffer database with WAL journal mode.

Models:
- DeleteSummary: Response model summarizing the number of deleted messages.

Logging:
- Uses a module-specific logger for operational logging.
"""

from app.config import BUFFER_DB
from shared.models.ledger import DeleteSummary

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

import sqlite3

from fastapi import APIRouter, Path

router = APIRouter()

TABLE = "conversation_messages"


def _open_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(BUFFER_DB, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


@router.delete(
    "/ledger/conversation/{conversation_id}/before/{message_id}",
    response_model=DeleteSummary,
)
def prune_conversation_messages(
    conversation_id: str = Path(...),
    message_id: int = Path(..., description="Prune EVERYTHING ≤ this id for the conversation"),
) -> DeleteSummary:
    """
    Delete messages from a conversation up to and including a specific message ID.

    Args:
        conversation_id (str): Unique identifier of the conversation to prune messages from.
        message_id (int): Message ID up to which (and including) all messages will be deleted.

    Returns:
        DeleteSummary: A summary containing the number of messages deleted from the conversation.
    """

    logger.debug(f"Deleting messages for conversation {conversation_id} up to message ID {message_id}")

    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"DELETE FROM {TABLE} WHERE conversation_id = ? AND id <= ?",
            (conversation_id, message_id),
        )
        deleted = cur.rowcount
        conn.commit()
        return DeleteSummary(deleted=deleted)


@router.delete(
    "/ledger/conversation/{conversation_id}",
    response_model=DeleteSummary,
)
def delete_conversation_buffer(
    conversation_id: str = Path(...),
) -> DeleteSummary:
    """
    Delete all messages for a specific conversation from the buffer database.

    Args:
        conversation_id (str): Unique identifier of the conversation to be completely deleted.

    Returns:
        DeleteSummary: A summary containing the number of messages deleted from the conversation.
    """

    logger.debug(f"Deleting all messages for conversation {conversation_id}")

    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {TABLE} WHERE conversation_id = ?", (conversation_id,))
        deleted = cur.rowcount
        conn.commit()
        return DeleteSummary(deleted=deleted)
