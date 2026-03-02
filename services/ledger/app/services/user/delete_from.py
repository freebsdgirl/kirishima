from shared.models.ledger import UserMessagesDeleteFromResponse

from app.util import _open_conn


TABLE = "user_messages"


def _delete_user_messages_from_row(user_id: str, row_id: int) -> UserMessagesDeleteFromResponse:
    """
    Delete all rows for user_id from row_id onward (inclusive).
    """
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id FROM {TABLE} WHERE id = ? AND user_id = ?",
            (row_id, user_id),
        )
        row = cur.fetchone()
        if not row:
            raise LookupError("Message row not found.")

        cur.execute(
            f"DELETE FROM {TABLE} WHERE user_id = ? AND id >= ?",
            (user_id, row_id),
        )
        deleted = cur.rowcount
        conn.commit()

    return UserMessagesDeleteFromResponse(
        deleted=deleted,
        first_deleted_row_id=row_id,
    )
