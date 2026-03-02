from shared.models.ledger import UserMessageEditResponse

from app.util import _open_conn


TABLE = "user_messages"


def _edit_user_message_content(user_id: str, row_id: int, content: str) -> UserMessageEditResponse:
    """
    Edit a user-owned row in user_messages and return before/after content.
    """
    trimmed_content = content.strip()
    if not trimmed_content:
        raise ValueError("Content cannot be empty.")

    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, user_id, role, content, tool_calls, function_call FROM {TABLE} WHERE id = ? AND user_id = ?",
            (row_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            raise LookupError("Message row not found.")

        db_row_id, db_user_id, role, before_content, tool_calls, function_call = row

        if role == "tool":
            raise ValueError("Tool rows cannot be edited.")
        if role not in ("user", "assistant"):
            raise ValueError("Only user and assistant rows can be edited.")
        if role == "assistant" and (tool_calls or function_call):
            raise ValueError("Tool call rows cannot be edited.")

        cur.execute(
            f"""
            UPDATE {TABLE}
            SET content = ?, updated_at = (STRFTIME('%Y-%m-%d %H:%M:%f','now'))
            WHERE id = ? AND user_id = ?
            """,
            (trimmed_content, db_row_id, db_user_id),
        )
        conn.commit()

        cur.execute(
            f"SELECT updated_at FROM {TABLE} WHERE id = ? AND user_id = ?",
            (db_row_id, db_user_id),
        )
        updated_row = cur.fetchone()
        if not updated_row:
            raise RuntimeError("Failed to read updated row.")

    return UserMessageEditResponse(
        row_id=db_row_id,
        user_id=db_user_id,
        role=role,
        before_content=before_content,
        after_content=trimmed_content,
        updated_at=updated_row[0],
    )
