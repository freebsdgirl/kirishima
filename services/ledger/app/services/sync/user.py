from shared.models.ledger import UserSyncRequest

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from app.util import _open_conn

import json

TABLE = "user_messages"


def _sync_user_buffer_helper(request: UserSyncRequest):
    """
    Internal helper for synchronizing user messages with the server-side ledger.

    This function handles complex message buffer synchronization logic for user messages, supporting:
    - Deduplication of messages
    - Handling consecutive user messages (after 500 errors)
    - Assistant message editing detection
    - Platform-specific logic

    Args:
        request: UserSyncRequest containing user_id (optional) and snapshot
    """
    user_id = request.user_id
    snapshot = request.snapshot
    
    # Default to config user_id if not provided
    if not user_id:
        with open('/app/config/config.json') as f:
            _config = json.load(f)
        user_id = _config.get("user_id")
    
    logger.debug(f"Syncing user buffer for {user_id}: {snapshot}")

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
            return

    # ----------------- Non‑API fast path -----------------
    if last_msg.platform != "api":
        with _open_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                f"INSERT INTO {TABLE} (user_id, platform, platform_msg_id, role, content, model, tool_calls, function_call, tool_call_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                _msg_fields(last_msg),
            )
            conn.commit()
            return

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
            return

        last_db_user = user_rows[-1][1] if user_rows else None

        # --- User message deduplication and assistant refresh logic ---
        if last_msg.role == "user":
            if last_db_user and last_msg.content == last_db_user[2]:
                # If duplicate user message, remove any subsequent assistant message
                if assistant_rows and assistant_rows[-1][0] > user_rows[-1][0]:
                    cur.execute(
                        f"DELETE FROM {TABLE} WHERE id = ?", (assistant_rows[-1][1][0],)
                    )
                    conn.commit()
                return
            
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
            
            # Insert the new user message
            cur.execute(
                f"INSERT INTO {TABLE} (user_id, platform, platform_msg_id, role, content, model, tool_calls, function_call, tool_call_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                _msg_fields(last_msg),
            )
            conn.commit()
            return

        # Handle assistant edit detection for non-user last messages
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
            return

        # Fallback append for other message types
        cur.execute(
            f"INSERT INTO {TABLE} (user_id, platform, platform_msg_id, role, content, model, tool_calls, function_call, tool_call_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            _msg_fields(last_msg),
        )
        conn.commit()
