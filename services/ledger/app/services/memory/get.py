from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from app.util import _open_conn

from shared.models.ledger import MemoryEntry
from app.services.topic.get_id import _get_topic_by_id

from fastapi import HTTPException, status


def _get_memory_by_id(memory_id: str):
    """
    Helper function to retrieve a memory from the database by its ID.

    Args:
        memory_id (str): The unique identifier of the memory.

    Returns:
        dict: A dictionary containing the memory details.
    
    Raises:
        HTTPException: If the memory does not exist.
    """
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found.")
        return MemoryEntry(
            id=row[0],
            memory=row[1],
            created_at=row[2],
            access_count=row[3],
            last_accessed=row[4]
        )

def _get_memory_keywords(memory_id: str):
    """
    Helper function to retrieve keywords associated with a memory.

    Args:
        memory_id (str): The unique identifier of the memory.

    Returns:
        list: A list of keywords associated with the memory.
    
    Raises:
        HTTPException: If there is an error fetching keywords.
    """
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT tag FROM memory_tags WHERE memory_id = ?", (memory_id,))
        tags = [row[0] for row in cur.fetchall()]
    return tags


def _get_memory_category(memory_id: str):
    """
    Helper function to retrieve the category associated with a memory.

    Args:
        memory_id (str): The unique identifier of the memory.

    Returns:
        str: The category of the memory, or None if not found.
    
    Raises:
        HTTPException: If there is an error fetching the category.
    """
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT category FROM memory_category WHERE memory_id = ?", (memory_id,))
        row = cur.fetchone()
        return row[0] if row else None


def _get_memory_topic(memory_id: str):
    """
    Helper function to retrieve the topic associated with a memory.

    Args:
        memory_id (str): The unique identifier of the memory.

    Returns:
        tuple: (topic_id, topic_name) tuple, or (None, None) if not found.
    
    Raises:
        HTTPException: If there is an error fetching the topic.
    """
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT topic_id FROM memory_topics WHERE memory_id = ?", (memory_id,))
        row = cur.fetchone()
        if row:
            topic_id = row[0]
            topic_data = _get_topic_by_id(topic_id)
            topic_name = topic_data.get("name") if topic_data else None
            return topic_id, topic_name
        else:
            return None, None


def _get_memory(memory_id: str):
    """
    Helper function to retrieve memory details including keywords, category, and topic.

    Args:
        memory_id (str): The unique identifier of the memory.

    Returns:
        dict: A dictionary containing the memory details, keywords, category, and topic.
    
    Raises:
        HTTPException: If the memory does not exist or if there is an error fetching details.
    """
    memory = _get_memory_by_id(memory_id)
    tags = _get_memory_keywords(memory_id)
    category = _get_memory_category(memory_id)
    topic_id, topic_name = _get_memory_topic(memory_id)

    return MemoryEntry(
        id=memory.id,
        memory=memory.memory,
        created_at=memory.created_at,
        access_count=memory.access_count,
        last_accessed=memory.last_accessed,
        keywords=tags,
        category=category,
        topic_id=topic_id,
        topic_name=topic_name
    )