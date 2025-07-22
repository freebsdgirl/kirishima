from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from app.util import _open_conn
from app.topic.util import topic_exists
from fastapi import HTTPException, status


def _get_memory_by_topic(topic_id: str):
    """
    Helper function to retrieve all memories associated with a specific topic.

    Args:
        topic_id (str): The unique identifier of the topic.

    Returns:
        list: A list of memory IDs associated with the topic.
    
    Raises:
        HTTPException: If the topic does not exist or if there are no memories for the topic.
    """
    if not topic_exists(topic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")

    with _open_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT memory_id FROM memory_topics WHERE topic_id = ?",
            (topic_id,)
        )
        memories = [row[0] for row in cursor.fetchall()]

    if not memories:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No memories found for this topic.")
    
    return memories
