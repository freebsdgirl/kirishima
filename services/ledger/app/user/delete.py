"""user_sync.py — 1‑on‑1 user buffer endpoints.

Endpoints:
    POST /ledger/user/{user_id}/sync              — existing sync w/ refresh+edit rules
    GET  /ledger/user/{user_id}/messages          — fetch all messages for user
    DELETE /ledger/user/{user_id}/before/{id}     — prune <= id (summarizer)
    DELETE /ledger/user/{user_id}                 — delete all for user
"""

from app.config import BUFFER_DB
from shared.models.ledger import  DeleteSummary

from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

import sqlite3
from typing import List

from fastapi import APIRouter, Path, Body

router = APIRouter()

TABLE = "user_messages"


def _open_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(BUFFER_DB, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


@router.delete("/ledger/user/{user_id}/before/{message_id}", response_model=DeleteSummary)
def prune_user_messages(
    user_id: str = Path(...),
    message_id: int = Path(..., description="Prune EVERYTHING ≤ this id for the user"),
    noop: bool = False,  # If True, log what would be deleted but do not delete
) -> DeleteSummary:
    """
    Delete messages for a specific user up to a given message ID.

    Removes all messages for the specified user with an ID less than or equal to the provided message ID.
    This allows for selective pruning of a user's message history.

    Args:
        user_id (str): The unique identifier of the user whose messages will be pruned.
        message_id (int): The maximum message ID to delete (inclusive).
        noop (bool): If True, only log what would be deleted, do not delete.

    Returns:
        DeleteSummary: An object containing the count of deleted messages.
    """

    logger.debug(f"Deleting messages for user {user_id} up to message ID {message_id} (noop={noop})")

    with _open_conn() as conn:
        cur = conn.cursor()
        if noop:
            cur.execute(
                f"SELECT id FROM {TABLE} WHERE user_id = ? AND id <= ?",
                (user_id, message_id),
            )
            ids = [row[0] for row in cur.fetchall()]
            logger.debug(f"NOOP: Would delete {len(ids)} messages: {ids}")
            return DeleteSummary(deleted=len(ids))
        else:
            cur.execute(
                f"DELETE FROM {TABLE} WHERE user_id = ? AND id <= ?",
                (user_id, message_id),
            )
            deleted = cur.rowcount
            conn.commit()
            return DeleteSummary(deleted=deleted)


@router.delete("/ledger/user/{user_id}", response_model=DeleteSummary)
def delete_user_buffer(user_id: str = Path(...)) -> DeleteSummary:
    """
    Delete all messages for a specific user from the buffer database.

    Performs a hard reset by removing all messages associated with the given user ID.
    Returns a summary of the number of messages deleted.

    Args:
        user_id (str): The unique identifier of the user whose messages will be deleted.

    Returns:
        DeleteSummary: An object containing the count of deleted messages.
    """

    """Delete ALL messages for the user (hard reset)."""

    logger.debug(f"Deleting all messages for user {user_id}")

    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {TABLE} WHERE user_id = ?", (user_id,))
        deleted = cur.rowcount
        conn.commit()
        return DeleteSummary(deleted=deleted)
