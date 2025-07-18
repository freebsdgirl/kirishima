"""
"""
from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from app.util import _open_conn
from app.topic.util import topic_exists
from app.memory.get import _get_memory_by_id, _get_memory_keywords, _get_memory_category, _get_memory_topic
from shared.models.ledger import MemoryEntry, MemoryListRequest
from fastapi import APIRouter, HTTPException, status
router = APIRouter()


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

    
@router.get("/memories/by-topic/{topic_id}")
def get_memory_by_topic(topic_id: str):
    memory_ids = _get_memory_by_topic(topic_id)
    memories = [_get_memory_by_id(mem_id) for mem_id in memory_ids]

    if not memories:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No memories found for this topic.")

    for memory in memories:
        memory.keywords = _get_memory_keywords(memory.id)
        memory.category = _get_memory_category(memory.id)
        memory.topic = _get_memory_topic(memory.id)

    return {"status": "success", "memories": [MemoryEntry(**memory.__dict__) for memory in memories]}