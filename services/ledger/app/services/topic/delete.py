from app.util import _open_conn

from shared.models.ledger import TopicDeleteRequest

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")


def _delete_topic(request: TopicDeleteRequest):
    """
    Helper function to delete a topic from the database by its ID.
    
    Args:
        request (TopicDeleteRequest): The request containing the topic ID to delete.
    
    Returns:
        int: The number of deleted topics (should be 1 if successful).
    """
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM topics WHERE id = ?", (request.topic_id,))
        conn.commit()
        return cur.rowcount