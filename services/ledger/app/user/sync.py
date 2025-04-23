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

from fastapi import APIRouter, Path, Body, BackgroundTasks
from app.user.summary import create_summaries

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
    background_tasks: BackgroundTasks = None
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
    print(f"[SYNC] user_id={user_id}")
    print(f"[SYNC] Incoming snapshot:")
    for i, msg in enumerate(snapshot):
        print(f"  {i}: role={msg.role}, content={msg.content!r}, platform={msg.platform}")

    if not snapshot:
        print("[SYNC] Empty snapshot, returning []")
        background_tasks.add_task(create_summaries, user_id)
        return []

    last_msg = snapshot[-1]
    print(f"[SYNC] Last message: role={last_msg.role}, content={last_msg.content!r}, platform={last_msg.platform}")

    # --- Edge case: consecutive user messages (likely after a 500) ---
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, role FROM {TABLE} WHERE user_id = ? ORDER BY id DESC LIMIT 1",
            (user_id,)
        )
        last_db_row = cur.fetchone()
        if last_db_row and last_db_row[1] == "user" and snapshot and snapshot[-1].role == "user":
            print(f"[SYNC] Edge case: consecutive user messages. Deleting most recent user message with id={last_db_row[0]}")
            cur.execute(f"DELETE FROM {TABLE} WHERE id = ?", (last_db_row[0],))
            conn.commit()
            # After deletion, return the updated buffer
            cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
            result = [CanonicalUserMessage(**dict(zip([col[0] for col in cur.description], row))) for row in cur.fetchall()]
            print(f"[SYNC] DB after deleting consecutive user: {[ (m.role, m.content) for m in result ]}")
            if last_msg.role == "assistant":
                background_tasks.add_task(create_summaries, user_id)
            return result

    # ----------------- Non‑API fast path -----------------
    if last_msg.platform != "api":
        print("[SYNC] Last message is not from 'api', inserting directly.")
        with _open_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO {TABLE} (user_id, platform, platform_msg_id, role, content) VALUES (?, ?, ?, ?, ?)",
                (user_id, last_msg.platform, last_msg.platform_msg_id, last_msg.role, last_msg.content),
            )
            conn.commit()
            cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
            result = [CanonicalUserMessage(**dict(zip([col[0] for col in cur.description], row))) for row in cur.fetchall()]
            print(f"[SYNC] DB after insert (non-api): {[ (m.role, m.content) for m in result ]}")
            if last_msg.role == "assistant":
                background_tasks.add_task(create_summaries, user_id)
            return result

    # ----------------- API logic -----------------
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, role, content FROM {TABLE} WHERE user_id = ? ORDER BY id",
            (user_id,),
        )
        rows = cur.fetchall()
        print(f"[SYNC] DB rows before sync: {rows}")

        user_rows      = [(idx, r) for idx, r in enumerate(rows) if r[1] == "user"]
        assistant_rows = [(idx, r) for idx, r in enumerate(rows) if r[1] == "assistant"]

        print(f"[SYNC] user_rows: {user_rows}")
        print(f"[SYNC] assistant_rows: {assistant_rows}")

        incoming_user      = [m for m in snapshot if m.role == "user"]
        incoming_assistant = [m for m in snapshot if m.role == "assistant"]

        print(f"[SYNC] incoming_user: {[ (m.content) for m in incoming_user ]}")
        print(f"[SYNC] incoming_assistant: {[ (m.content) for m in incoming_assistant ]}")

        # Seed brand‑new buffer with exactly the last incoming message
        if not rows:
            print("[SYNC] DB is empty, seeding with last incoming message.")
            cur.execute(
                f"INSERT INTO {TABLE} (user_id, platform, platform_msg_id, role, content) VALUES (?, ?, ?, ?, ?)",
                (user_id, last_msg.platform, last_msg.platform_msg_id, last_msg.role, last_msg.content),
            )
            conn.commit()
            cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
            result = [CanonicalUserMessage(**dict(zip([col[0] for col in cur.description], row))) for row in cur.fetchall()]
            print(f"[SYNC] DB after seed: {[ (m.role, m.content) for m in result ]}")
            if last_msg.role == "assistant":
                background_tasks.add_task(create_summaries, user_id)
            return result

        last_db_user = user_rows[-1][1] if user_rows else None
        last_incoming_user = incoming_user[-1] if incoming_user else None
        print(f"[SYNC] last_db_user: {last_db_user}")
        print(f"[SYNC] last_incoming_user: {getattr(last_incoming_user, 'content', None)}")

        # --- User message deduplication and assistant refresh logic ---
        if last_msg.role == "user":
            last_db_user = user_rows[-1][1] if user_rows else None
            if last_db_user and last_msg.content == last_db_user[2]:
                print("[SYNC] Rule: last incoming user matches last db user. Deleting last assistant if present.")
                if assistant_rows and assistant_rows[-1][0] > user_rows[-1][0]:
                    print(f"[SYNC] Deleting assistant message with id={assistant_rows[-1][1][0]}")
                    cur.execute(
                        f"DELETE FROM {TABLE} WHERE id = ?", (assistant_rows[-1][1][0],)
                    )
                    conn.commit()
                else:
                    print("[SYNC] No assistant message to delete.")
                # Always return the full buffer
                cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
                result = [CanonicalUserMessage(**dict(zip([col[0] for col in cur.description], row))) for row in cur.fetchall()]
                print(f"[SYNC] DB after user deduplication/assistant delete: {[ (m.role, m.content) for m in result ]}")
                if last_msg.role == "assistant":
                    background_tasks.add_task(create_summaries, user_id)
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
                    print(f"[SYNC] Assistant edit detected before user message. Updating assistant id={last_db_assistant_id}")
                    cur.execute(
                        f"UPDATE {TABLE} SET content = ?, updated_at = (STRFTIME('%Y-%m-%d %H:%M:%f','now')) WHERE id = ?",
                        (incoming_assistant_content, last_db_assistant_id),
                    )
                    conn.commit()
            print("[SYNC] Appending new user message.")
            cur.execute(
                f"INSERT INTO {TABLE} (user_id, platform, platform_msg_id, role, content) VALUES (?, ?, ?, ?, ?)",
                (user_id, last_msg.platform, last_msg.platform_msg_id, last_msg.role, last_msg.content),
            )
            conn.commit()
            cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
            result = [CanonicalUserMessage(**dict(zip([col[0] for col in cur.description], row))) for row in cur.fetchall()]
            print(f"[SYNC] DB after appending user: {[ (m.role, m.content) for m in result ]}")
            if last_msg.role == "assistant":
                background_tasks.add_task(create_summaries, user_id)
            return result

        # Rule 2 – edit assistant
        if (
            len(incoming_user) >= 2 and
            last_db_user and incoming_user[-2].content == last_db_user[2] and
            incoming_assistant
        ):
            print("[SYNC] Rule 2 triggered: edit assistant.")
            last_db_assistant_id = assistant_rows[-1][1][0] if assistant_rows else None
            print(f"[SYNC] last_db_assistant_id: {last_db_assistant_id}")
            if (
                last_db_assistant_id and
                incoming_assistant[-1].content != assistant_rows[-1][1][2]
            ):
                print(f"[SYNC] Updating assistant message id={last_db_assistant_id} with new content.")
                cur.execute(
                    f"UPDATE {TABLE} SET content = ?, updated_at = (STRFTIME('%Y-%m-%d %H:%M:%f','now')) WHERE id = ?",
                    (incoming_assistant[-1].content, last_db_assistant_id),
                )
                conn.commit()
            else:
                print("[SYNC] No update needed for assistant message.")
            # Always return the full buffer
            cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
            result = [CanonicalUserMessage(**dict(zip([col[0] for col in cur.description], row))) for row in cur.fetchall()]
            print(f"[SYNC] DB after assistant edit: {[ (m.role, m.content) for m in result ]}")
            if last_msg.role == "assistant":
                background_tasks.add_task(create_summaries, user_id)
            return result

        # Rule 3 – fallback append
        print("[SYNC] Rule 3 triggered: fallback append. Inserting last message.")
        cur.execute(
            f"INSERT INTO {TABLE} (user_id, platform, platform_msg_id, role, content) VALUES (?, ?, ?, ?, ?)",
            (user_id, last_msg.platform, last_msg.platform_msg_id, last_msg.role, last_msg.content),
        )
        conn.commit()
        cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
        result = [CanonicalUserMessage(**dict(zip([col[0] for col in cur.description], row))) for row in cur.fetchall()]
        print(f"[SYNC] DB after fallback append: {[ (m.role, m.content) for m in result ]}")
        if last_msg.role == "assistant":
            background_tasks.add_task(create_summaries, user_id)
        return result
