"""
This module provides an API endpoint and synchronization logic for user message buffers in the ledger service.

Functions:
    _open_conn() -> sqlite3.Connection:
        Opens a SQLite database connection to the buffer database with WAL journal mode enabled.

    sync_user_buffer(
        user_id: str,
        snapshot: List[RawUserMessage]
        FastAPI endpoint to synchronize a user's message buffer with the server-side ledger.
        Receives a snapshot of user and assistant messages, applies synchronization rules, and updates the database accordingly.

        Synchronization Logic:

Attributes:
    BUFFER_DB (str): Path to the buffer database.
    TABLE (str): Name of the user messages table.
    router (APIRouter): FastAPI router for the sync endpoint.
    logger: Logger instance for this module.
"""

from app.config import BUFFER_DB
from shared.models.ledger import RawUserMessage, CanonicalUserMessage

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

import sqlite3
from typing import List

from fastapi import APIRouter, Path, Body

router = APIRouter()

TABLE = "user_messages"


def _open_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(BUFFER_DB, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


@router.post("/ledger/user/{user_id}/sync", response_model=List[CanonicalUserMessage])
def sync_user_buffer(
    user_id: str = Path(..., description="Unique user identifier"),
    snapshot: List[RawUserMessage] = Body(..., embed=True)
) -> List[CanonicalUserMessage]:
    """
    Synchronizes the user's message buffer with the server-side ledger.

    This endpoint receives a snapshot of user and assistant messages and applies synchronization logic to ensure the server's message buffer reflects the latest state.

    Args:
        user_id (str): Unique user identifier, provided as a path parameter.
        snapshot (List[RawUserMessage]): List of incoming user and assistant messages, provided in the request body.

    Returns:
        List[CanonicalUserMessage]: The updated list of canonical user messages after synchronization.

    Logic:
        - If the snapshot is empty, returns an empty list.
        - If the last message is not from the "api" platform, inserts it directly and returns the updated buffer.
        - If the buffer is empty, seeds it with the last incoming message.
        - If the last incoming user message matches the last user message in the database, deletes the last assistant message (refresh assistant).
        - If the second-to-last incoming user message matches the last user message in the database and there is an incoming assistant message, updates the last assistant message (edit assistant).
        - Otherwise, appends the last incoming message to the buffer (fallback append).

    Note:
        The function uses a database connection to persist and retrieve messages, and applies different synchronization rules based on the state of the incoming snapshot and the existing buffer.
    """
    logger.debug(f"Syncing user buffer for {user_id}: {snapshot}")

    if not snapshot:
        return []

    last_msg = snapshot[-1]

    # ----------------- Non‑API fast path -----------------
    if last_msg.platform != "api":
        with _open_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO {TABLE} (user_id, platform, platform_msg_id, role, content) VALUES (?, ?, ?, ?, ?)",
                (user_id, last_msg.platform, last_msg.platform_msg_id, last_msg.role, last_msg.content),
            )
            conn.commit()
            cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
            return [CanonicalUserMessage(*row) for row in cur.fetchall()]

    # ----------------- API logic -----------------
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, role, content FROM {TABLE} WHERE user_id = ? ORDER BY id",
            (user_id,),
        )
        rows = cur.fetchall()

        user_rows      = [(idx, r) for idx, r in enumerate(rows) if r[1] == "user"]
        assistant_rows = [(idx, r) for idx, r in enumerate(rows) if r[1] == "assistant"]

        incoming_user      = [m for m in snapshot if m.role == "user"]
        incoming_assistant = [m for m in snapshot if m.role == "assistant"]

        # Seed brand‑new buffer with exactly the last incoming message
        if not rows:
            cur.execute(
                f"INSERT INTO {TABLE} (user_id, platform, platform_msg_id, role, content) VALUES (?, ?, ?, ?, ?)",
                (user_id, last_msg.platform, last_msg.platform_msg_id, last_msg.role, last_msg.content),
            )
            conn.commit()
            cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
            return [CanonicalUserMessage(*row) for row in cur.fetchall()]

        last_db_user = user_rows[-1][1] if user_rows else None
        last_incoming_user = incoming_user[-1] if incoming_user else None

        # Rule 1 – refresh assistant
        if last_incoming_user and last_db_user and last_incoming_user.content == last_db_user[2]:
            if assistant_rows:
                cur.execute(
                    f"DELETE FROM {TABLE} WHERE id = ?", (assistant_rows[-1][1][0],)
                )
                conn.commit()
            return []

        # Rule 2 – edit assistant
        if (
            len(incoming_user) >= 2 and
            last_db_user and incoming_user[-2].content == last_db_user[2] and
            incoming_assistant
        ):
            last_db_assistant_id = assistant_rows[-1][1][0] if assistant_rows else None
            if (
                last_db_assistant_id and
                incoming_assistant[-1].content != assistant_rows[-1][1][2]
            ):
                cur.execute(
                    f"UPDATE {TABLE} SET content = ?, updated_at = (STRFTIME('%Y-%m-%d %H:%M:%f','now')) WHERE id = ?",
                    (incoming_assistant[-1].content, last_db_assistant_id),
                )
                conn.commit()
            return []

        # Rule 3 – fallback append
        cur.execute(
            f"INSERT INTO {TABLE} (user_id, platform, platform_msg_id, role, content) VALUES (?, ?, ?, ?, ?)",
            (user_id, last_msg.platform, last_msg.platform_msg_id, last_msg.role, last_msg.content),
        )
        conn.commit()
        cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
        return [CanonicalUserMessage(*row) for row in cur.fetchall()]
