from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

from app.util import _open_conn

from typing import List


def _get_active_users() -> List[str]:
    """
    Internal helper to retrieve all unique user IDs from the database.
    
    Returns:
        List[str]: A list of unique user IDs found in the user messages database.
    """
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT user_id FROM user_messages"
        )
        user_ids = [row[0] for row in cur.fetchall()]
        logger.debug(f"Found {len(user_ids)} unique user IDs in the database.")
        return user_ids