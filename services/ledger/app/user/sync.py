"""
This module provides synchronization logic for user message buffers in the ledger service.

It exposes a FastAPI router with an endpoint to synchronize a user's message buffer with the server-side ledger,
handling deduplication, message edits, and appending new messages. The synchronization process supports both API
and non-API platforms, and ensures the server buffer accurately reflects the latest client state.

Key Features:
- Deduplication of consecutive user messages to prevent duplicates after errors or retries.
- Handling of assistant message edits, updating the server buffer when the assistant's response changes.
- Appending new messages to the buffer, with logic to seed new buffers and handle edge cases.
- Optional result limiting to control the number of messages returned.
- Integration points for background summary creation (currently commented out).

Dependencies:
- FastAPI for API routing and request handling.
- SQLite for persistent message storage.
- Pydantic models for message validation and serialization.
- Logging for debug and traceability.

Functions:
- _open_conn: Opens a SQLite connection with WAL mode enabled.
- sync_user_buffer: FastAPI endpoint to synchronize the user's message buffer, applying deduplication,
    edit detection, and append logic based on the incoming snapshot.

Table:
- user_messages: Stores user and assistant messages with metadata for synchronization.

Usage:
Import this module and include its router in your FastAPI application to enable message buffer synchronization
for user conversations in the ledger service.
"""

from shared.models.ledger import RawUserMessage, CanonicalUserMessage

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

import sqlite3
from typing import List, Optional
import json

from fastapi import APIRouter, Path, Body, BackgroundTasks
#from app.user.summary import create_summaries

router = APIRouter()

TABLE = "user_messages"


def _open_conn() -> sqlite3.Connection:
    with open('/app/config/config.json') as f:
        _config = json.load(f)

    db = _config["db"]["ledger"]
    conn = sqlite3.connect(db, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def ensure_first_user(messages):
    for i, msg in enumerate(messages):
        if msg.role == "user":
            return messages[i:]
    return []


@router.post("/ledger/user/{user_id}/sync", response_model=List[CanonicalUserMessage])
def sync_user_buffer(
    user_id: str = Path(..., description="Unique user identifier"),
    snapshot: List[RawUserMessage] = Body(..., embed=True),
    background_tasks: BackgroundTasks = None,
    limit: Optional[int] = 25
) -> List[CanonicalUserMessage]:
    """
    Synchronize a user's message buffer with the server-side ledger.

    This endpoint handles complex message buffer synchronization logic for a given user, supporting:
    - Deduplication of messages
    - Handling consecutive user messages
    - Editing assistant messages
    - Appending new messages
    - Optional result limiting

    Args:
        user_id (str): Unique identifier for the user
        snapshot (List[RawUserMessage]): Snapshot of user and assistant messages
        background_tasks (BackgroundTasks, optional): Background task handler
        limit (int, optional): Maximum number of messages to return, defaults to 15

    Returns:
        List[CanonicalUserMessage]: Synchronized and processed message buffer
    """
    logger.debug(f"Syncing user buffer for {user_id}: {snapshot}")

    #if not snapshot:
    #    background_tasks.add_task(create_summaries, user_id)
    #    return []

    # Do NOT filter snapshot; allow any role at the start
    last_msg = snapshot[-1]

    def _msg_fields(msg):
        return (
            user_id,
            msg.platform,
            getattr(msg, 'platform_msg_id', None),
            msg.role,
            msg.content,
            getattr(msg, 'model', None),
            json.dumps(getattr(msg, 'tool_calls', None)) if getattr(msg, 'tool_calls', None) is not None else None,
            json.dumps(getattr(msg, 'function_call', None)) if getattr(msg, 'function_call', None) is not None else None,
            getattr(msg, 'tool_call_id', None) if getattr(msg, 'tool_call_id', None) is not None else None
        )

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
            # After deletion, insert the new incoming user message
            cur.execute(
                f"INSERT INTO {TABLE} (user_id, platform, platform_msg_id, role, content, model, tool_calls, function_call, tool_call_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                _msg_fields(last_msg),
            )
            conn.commit()
            # After insertion, return the updated buffer
            cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
            colnames = [desc[0] for desc in cur.description]
            result = [
                CanonicalUserMessage(**{
                    **dict(zip(colnames, row)),
                    'tool_calls': json.loads(row[colnames.index('tool_calls')]) if row[colnames.index('tool_calls')] else None,
                    'function_call': json.loads(row[colnames.index('function_call')]) if row[colnames.index('function_call')] else None,
                    'tool_call_id': row[colnames.index('tool_call_id')] if 'tool_call_id' in colnames else None,
                }) for row in cur.fetchall()
            ]
            if limit is not None:
                result = result[-limit:]
                result = ensure_first_user(result)
                return result
            else:
                result = ensure_first_user(result)
                return result

    # ----------------- Non‑API fast path -----------------
    if last_msg.platform != "api":
        with _open_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO {TABLE} (user_id, platform, platform_msg_id, role, content, model, tool_calls, function_call, tool_call_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                _msg_fields(last_msg),
            )
            conn.commit()
            cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
            colnames = [desc[0] for desc in cur.description]
            result = [
                CanonicalUserMessage(**{
                    **dict(zip(colnames, row)),
                    'tool_calls': json.loads(row[colnames.index('tool_calls')]) if row[colnames.index('tool_calls')] else None,
                    'function_call': json.loads(row[colnames.index('function_call')]) if row[colnames.index('function_call')] else None,
                    'tool_call_id': row[colnames.index('tool_call_id')] if 'tool_call_id' in colnames else None,
                }) for row in cur.fetchall()
            ]
            result = ensure_first_user(result)
            #if last_msg.role == "assistant":
                #background_tasks.add_task(create_summaries, user_id)
            if limit is not None:
                result = result[-limit:]
                result = ensure_first_user(result)
                return result
            else:
                result = ensure_first_user(result)
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
                f"INSERT INTO {TABLE} (user_id, platform, platform_msg_id, role, content, model, tool_calls, function_call, tool_call_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                _msg_fields(last_msg),
            )
            conn.commit()
            cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
            colnames = [desc[0] for desc in cur.description]
            result = [
                CanonicalUserMessage(**{
                    **dict(zip(colnames, row)),
                    'tool_calls': json.loads(row[colnames.index('tool_calls')]) if row[colnames.index('tool_calls')] else None,
                    'function_call': json.loads(row[colnames.index('function_call')]) if row[colnames.index('function_call')] else None,
                    'tool_call_id': row[colnames.index('tool_call_id')] if 'tool_call_id' in colnames else None,
                }) for row in cur.fetchall()
            ]
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
                colnames = [desc[0] for desc in cur.description]
                result = [
                    CanonicalUserMessage(**{
                        **dict(zip(colnames, row)),
                        'tool_calls': json.loads(row[colnames.index('tool_calls')]) if row[colnames.index('tool_calls')] else None,
                        'function_call': json.loads(row[colnames.index('function_call')]) if row[colnames.index('function_call')] else None,
                        'tool_call_id': row[colnames.index('tool_call_id')] if 'tool_call_id' in colnames else None,
                    }) for row in cur.fetchall()
                ]
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
                f"INSERT INTO {TABLE} (user_id, platform, platform_msg_id, role, content, model, tool_calls, function_call, tool_call_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                _msg_fields(last_msg),
            )
            conn.commit()
            cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
            colnames = [desc[0] for desc in cur.description]
            result = [
                CanonicalUserMessage(**{
                    **dict(zip(colnames, row)),
                    'tool_calls': json.loads(row[colnames.index('tool_calls')]) if row[colnames.index('tool_calls')] else None,
                    'function_call': json.loads(row[colnames.index('function_call')]) if row[colnames.index('function_call')] else None,
                    'tool_call_id': row[colnames.index('tool_call_id')] if 'tool_call_id' in colnames else None,
                }) for row in cur.fetchall()
            ]
            #if last_msg.role == "assistant":
                #background_tasks.add_task(create_summaries, user_id)
            if limit is not None:
                result = result[-limit:]
                result = ensure_first_user(result)
                return result
            else:
                result = ensure_first_user(result)
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
            colnames = [desc[0] for desc in cur.description]
            result = [
                CanonicalUserMessage(**{
                    **dict(zip(colnames, row)),
                    'tool_calls': json.loads(row[colnames.index('tool_calls')]) if row[colnames.index('tool_calls')] else None,
                    'function_call': json.loads(row[colnames.index('function_call')]) if row[colnames.index('function_call')] else None,
                    'tool_call_id': row[colnames.index('tool_call_id')] if 'tool_call_id' in colnames else None,
                }) for row in cur.fetchall()
            ]
            #if last_msg.role == "assistant":
                #background_tasks.add_task(create_summaries, user_id)
            if limit is not None:
                result = result[-limit:]
                result = ensure_first_user(result)
                return result
            else:
                result = ensure_first_user(result)
                return result

        # Rule 3 – fallback append
        cur.execute(
            f"INSERT INTO {TABLE} (user_id, platform, platform_msg_id, role, content, model, tool_calls, function_call, tool_call_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _msg_fields(last_msg),
        )
        conn.commit()
        cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
        colnames = [desc[0] for desc in cur.description]
        result = [
            CanonicalUserMessage(**{
                **dict(zip(colnames, row)),
                'tool_calls': json.loads(row[colnames.index('tool_calls')]) if row[colnames.index('tool_calls')] else None,
                'function_call': json.loads(row[colnames.index('function_call')]) if row[colnames.index('function_call')] else None,
                'tool_call_id': row[colnames.index('tool_call_id')] if 'tool_call_id' in colnames else None,
            }) for row in cur.fetchall()
        ]
        #if last_msg.role == "assistant":
            #background_tasks.add_task(create_summaries, user_id)
        if limit is not None:
            result = result[-limit:]
            result = ensure_first_user(result)
            return result
        else:
            result = ensure_first_user(result)
            return result
