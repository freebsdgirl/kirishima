from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from app.util import _open_conn
from app.services.memory.util import _memory_exists

from app.services.topic.util import _topic_exists

from fastapi import HTTPException, status


def _memory_assign_topic(memory_id: str, topic_id: str):
    """
    Assign a topic to a memory by inserting a record into the `memory_topics` table.
    
    Args:
        memory_id (str): The ID of the memory to assign the topic to.
        topic_id (str): The ID of the topic to assign.

    Raises:
        HTTPException: If the memory or topic does not exist, or if an error occurs during the database operation.
    """
    if not _memory_exists(memory_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found.")
    
    if not _topic_exists(topic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")

    try:
        with _open_conn() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO memory_topics (memory_id, topic_id) VALUES (?, ?)",
                (memory_id, topic_id)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error assigning topic {topic_id} to memory {memory_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unexpected error occurred.")

    logger.info(f"Topic {topic_id} assigned to memory {memory_id}.")

