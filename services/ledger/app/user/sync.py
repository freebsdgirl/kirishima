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
from typing import List, Optional

from fastapi import APIRouter, Path, Body, BackgroundTasks
#from app.user.summary import create_summaries

router = APIRouter()

TABLE = "user_messages"


def _open_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(BUFFER_DB, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


@router.post("/ledger/user/{user_id}/sync", response_model=List[CanonicalUserMessage])
def sync_user_buffer(
    user_id: str = Path(..., description="Unique user identifier"),
    snapshot: List[RawUserMessage] = Body(..., embed=True),
    background_tasks: BackgroundTasks = None,
    limit: Optional[int] = 15
) -> List[CanonicalUserMessage]:
    """
    Synchronizes the user's message buffer with the database, handling deduplication, edits, and appends.

    This endpoint receives a snapshot of user and assistant messages and ensures the database reflects the latest state,
    handling various edge cases such as consecutive user messages, deduplication, and assistant message edits.

    Args:
        user_id (str): Unique user identifier, provided as a path parameter.
        snapshot (List[RawUserMessage]): List of incoming user and assistant messages, provided in the request body.
        background_tasks (BackgroundTasks, optional): FastAPI background task manager for deferred processing.
        limit (Optional[int], default=30): Maximum number of messages to return in the response.

    Returns:
        List[CanonicalUserMessage]: The updated list of canonical user messages, up to the specified limit.

    Behavior:
        - If the snapshot is empty, triggers background summary creation and returns an empty list.
        - Handles edge cases such as consecutive user messages (e.g., after a server error) by removing duplicates.
        - For non-API platforms, appends the last message directly to the database.
        - For API-originated messages, performs deduplication, assistant message edits, and appends as needed.
        - Always returns the latest buffer of messages, limited by the `limit` parameter.
    """
    logger.debug(f"Syncing user buffer for {user_id}: {snapshot}")

    #if not snapshot:
    #    background_tasks.add_task(create_summaries, user_id)
    #    return []

    last_msg = snapshot[-1]

    # --- Edge case: consecutive user messages (likely after a 500) ---
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, role FROM {TABLE} WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        last_db_row = cur.fetchone()
        if last_db_row and last_db_row[1] == "user" and snapshot and snapshot[-1].role == "user":
            cur.execute(f"DELETE FROM {TABLE} WHERE id = ?", (last_db_row[0],))
            conn.commit()
            # After deletion, return the updated buffer
            cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
            result = [CanonicalUserMessage(**dict(zip([col[0] for col in cur.description], row))) for row in cur.fetchall()]
            #if last_msg.role == "assistant":
                #background_tasks.add_task(create_summaries, user_id)
            if limit is not None:
                return result[-limit:]
            else:
                return result

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
            result = [CanonicalUserMessage(**dict(zip([col[0] for col in cur.description], row))) for row in cur.fetchall()]
            #if last_msg.role == "assistant":
                #background_tasks.add_task(create_summaries, user_id)
            if limit is not None:
                return result[-limit:]
            else:
                return result

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
            result = [CanonicalUserMessage(**dict(zip([col[0] for col in cur.description], row))) for row in cur.fetchall()]
            #if last_msg.role == "assistant":
                #background_tasks.add_task(create_summaries, user_id)
            if limit is not None:
                return result[-limit:]
            else:
                return result

        last_db_user = user_rows[-1][1] if user_rows else None
        last_incoming_user = incoming_user[-1] if incoming_user else None

        # --- User message deduplication and assistant refresh logic ---
        if last_msg.role == "user":
            last_db_user = user_rows[-1][1] if user_rows else None
            if last_db_user and last_msg.content == last_db_user[2]:
                if assistant_rows and assistant_rows[-1][0] > user_rows[-1][0]:
                    cur.execute(
                        f"DELETE FROM {TABLE} WHERE id = ?", (assistant_rows[-1][1][0],)
                    )
                    conn.commit()
                # Always return the full buffer
                cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
                result = [CanonicalUserMessage(**dict(zip([col[0] for col in cur.description], row))) for row in cur.fetchall()]
                #if last_msg.role == "assistant":
                    #background_tasks.add_task(create_summaries, user_id)
                if limit is not None:
                    return result[-limit:]
                else:
                    return result
            # --- Check for assistant edit before appending user ---
            if (
                len(snapshot) >= 2 and
                snapshot[-2].role == "assistant" and
                assistant_rows
            ):
                incoming_assistant_content = snapshot[-2].content
                last_db_assistant_content = assistant_rows[-1][1][2]
                last_db_assistant_id = assistant_rows[-1][1][0]
                if incoming_assistant_content != last_db_assistant_content:
                    cur.execute(
                        f"UPDATE {TABLE} SET content = ?, updated_at = (STRFTIME('%Y-%m-%d %H:%M:%f','now')) WHERE id = ?",
                        (incoming_assistant_content, last_db_assistant_id),
                    )
                    conn.commit()
            cur.execute(
                f"INSERT INTO {TABLE} (user_id, platform, platform_msg_id, role, content) VALUES (?, ?, ?, ?, ?)",
                (user_id, last_msg.platform, last_msg.platform_msg_id, last_msg.role, last_msg.content),
            )
            conn.commit()
            cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
            result = [CanonicalUserMessage(**dict(zip([col[0] for col in cur.description], row))) for row in cur.fetchall()]
            #if last_msg.role == "assistant":
                #background_tasks.add_task(create_summaries, user_id)
            if limit is not None:
                return result[-limit:]
            else:
                return result

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
            # Always return the full buffer
            cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
            result = [CanonicalUserMessage(**dict(zip([col[0] for col in cur.description], row))) for row in cur.fetchall()]
            #if last_msg.role == "assistant":
                #background_tasks.add_task(create_summaries, user_id)
            if limit is not None:
                return result[-limit:]
            else:
                return result

        # Rule 3 – fallback append
        cur.execute(
            f"INSERT INTO {TABLE} (user_id, platform, platform_msg_id, role, content) VALUES (?, ?, ?, ?, ?)",
            (user_id, last_msg.platform, last_msg.platform_msg_id, last_msg.role, last_msg.content),
        )
        conn.commit()
        cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
        result = [CanonicalUserMessage(**dict(zip([col[0] for col in cur.description], row))) for row in cur.fetchall()]
        #if last_msg.role == "assistant":
            #background_tasks.add_task(create_summaries, user_id)
        if limit is not None:
            return result[-limit:]
        else:
            return result
