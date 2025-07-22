"""
This module provides synchronization logic for user message buffers in the ledger service.

It exposes a FastAPI router with an endpoint to synchronize a user's message buffer with the server-side ledger,
handling deduplication, consecutive user messages, assistant message edits, and appending new messages.
The module interacts with a SQLite database to persist and update message history.

Functions:
    _open_conn(): Opens a SQLite connection using configuration from a JSON file.
    ensure_first_user(messages): Ensures the returned message list starts with a user message.
    sync_user_buffer(user_id, snapshot, background_tasks, limit): FastAPI endpoint to synchronize a user's message buffer.

Key Features:
    - Deduplication of user and assistant messages
    - Handling of consecutive user messages (e.g., after server errors)
    - Editing of assistant messages if the content changes
    - Appending new messages to the ledger
    - Optional limiting of returned message history
    - Ensures the message buffer always starts with a user message

Models:
    - RawUserMessage: Incoming message format from the client
    - CanonicalUserMessage: Server-side canonical message format

Database Table:
    - user_messages: Stores message history for each user

Logging:
    - Uses a shared logger for debug and operational messages

"""

from shared.models.ledger import RawUserMessage, CanonicalUserMessage, UserSyncRequest
from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

import json
from typing import List
from fastapi import APIRouter, Path, Body, BackgroundTasks
from app.util import _open_conn

router = APIRouter()

TABLE = "user_messages"


def ensure_first_user(messages):
    for i, msg in enumerate(messages):
        if msg.role == "user":
            return messages[i:]
    return []


def _sync_user_buffer_helper(request: UserSyncRequest) -> List[CanonicalUserMessage]:
    """
    Internal helper for synchronizing a user's message buffer with the server-side ledger.

    This function handles complex message buffer synchronization logic for a given user, supporting:
    - Deduplication of messages
    - Handling consecutive user messages
    - Editing assistant messages
    - Appending new messages
    - Optional result limiting

    Args:
        request: UserSyncRequest containing user_id and snapshot

    Returns:
        List[CanonicalUserMessage]: Synchronized and processed message buffer
    """
    user_id = request.user_id
    snapshot = request.snapshot
    
    logger.debug(f"Syncing user buffer for {user_id}: {snapshot}")

    # Load configuration to determine the message limit
    with open('/app/config/config.json') as f:
            _config = json.load(f)
    # if turns isn't set, default to 15
    limit = _config.get("ledger", {}).get("turns", 15)

    #if not snapshot:
    #    background_tasks.add_task(create_summaries, user_id)
    #    return []

    # Do NOT filter snapshot; allow any role at the start.
    # We do this so we can sync our pseudo tool calls where we're injecting tools output that the assistant
    # didn't actually ask for prior to sending it the conversation log. we don't always sync to buffer for
    # that output, but the option is there.
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

    # Continue with rest of synchronization logic...
    # [Complex logic continues here - keeping existing implementation]
    
    # The full implementation continues for 200+ more lines...
    # For now, I'll just copy the rest of the function rather than break it up further

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
            # Only update if this is truly an edit scenario (same user message but different assistant response)
            if (
                len(snapshot) >= 2 and
                snapshot[-2].role == "assistant" and
                assistant_rows and
                user_rows and
                len(incoming_user) >= 1 and
                incoming_user[-1].content == user_rows[-1][1][2]  # Same user message as last in DB
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


@router.post("/user/{user_id}/sync", response_model=List[CanonicalUserMessage])
def sync_user_buffer(
    user_id: str = Path(..., description="Unique user identifier"),
    snapshot: List[RawUserMessage] = Body(..., embed=True),
    background_tasks: BackgroundTasks = None
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

    Returns:
        List[CanonicalUserMessage]: Synchronized and processed message buffer
    """
    request = UserSyncRequest(user_id=user_id, snapshot=snapshot)
    return _sync_user_buffer_helper(request)
