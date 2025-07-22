from shared.models.ledger import UserLastMessageRequest

from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

from app.util import _open_conn


def _get_last_message_timestamp(request: UserLastMessageRequest) -> str:
    """
    Internal helper to retrieve the timestamp of the most recent message sent by a specific user.

    Args:
        request: UserLastMessageRequest containing user_id

    Returns:
        str: The timestamp of the latest message sent by the user in the 'created_at' field,
             or an empty string if no messages are found.
    """
    user_id = request.user_id
    
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT created_at FROM user_messages WHERE user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,))
        row = cur.fetchone()
        return row[0] if row else ""