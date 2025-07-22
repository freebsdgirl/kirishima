from shared.models.ledger import DeleteUserMessagesRequest

from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

from app.services.user.util import _get_period_range
from app.util import _open_conn

TABLE = "user_messages"


def _delete_user_messages(request: DeleteUserMessagesRequest) -> int:
    """
    Internal helper to delete user messages by user ID, optionally filtered by period and date.

    Args:
        user_id (str): The unique identifier of the user whose messages will be deleted.
        period (Optional[str]): Time period to filter messages.
        date (Optional[str]): Date in YYYY-MM-DD format.

    Returns:
        int: The number of deleted messages.
    """
    user_id = request.user_id
    period = request.period
    date = request.date
    logger.debug(f"Deleting messages for user {user_id} (period={period}, date={date})")

    with _open_conn() as conn:
        cur = conn.cursor()
        if period:
            start, end = _get_period_range(period, date)
            cur.execute(
                f"DELETE FROM {TABLE} WHERE user_id = ? AND created_at >= ? AND created_at <= ?",
                (user_id, start.strftime("%Y-%m-%d %H:%M:%S.%f"), end.strftime("%Y-%m-%d %H:%M:%S.%f")),
            )
        else:
            cur.execute(
                f"""
                DELETE FROM {TABLE}
                WHERE user_id = ?
                  AND ROWID NOT IN (
                    SELECT ROWID FROM {TABLE}
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT 10
                  )
                """,
                (user_id, user_id)
            )
        deleted = cur.rowcount
        conn.commit()
        return deleted