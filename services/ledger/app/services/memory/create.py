from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from shared.models.ledger import MemoryEntry
from app.util import _open_conn

import uuid
from datetime import datetime

from fastapi import HTTPException, status


def _memory_add_keywords(memory_id: str, keywords: list):
    """
    Helper function to add keywords to a memory entry in the database.

    Args:
        memory_id (str): The unique identifier of the memory entry.
        keywords (list): A list of keywords to associate with the memory.
    """
    with _open_conn() as conn:
        cursor = conn.cursor()
        for tag in keywords:
            tag_lower = tag.lower()
            cursor.execute(
                """
                INSERT OR IGNORE INTO memory_tags (memory_id, tag)
                VALUES (?, ?)
                """,
                (memory_id, tag_lower)
            )
        conn.commit()


def _memory_add_category(memory_id: str, category: str):
    """
    Helper function to add a category to a memory entry in the database.

    Args:
        memory_id (str): The unique identifier of the memory entry.
        category (str): The category to associate with the memory.
    """

    allowed_categories = [
        "Health", "Career", "Family", "Personal", "Technical Projects",
        "Social", "Finance", "Self-care", "Environment", "Hobbies",
        "Admin", "Philosophy"
    ]
    if category not in allowed_categories:
        logger.debug(f"Invalid category: {category}.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category: {category}. Allowed categories are: {', '.join(allowed_categories)}"
        )
    with _open_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO memory_category (memory_id, category)
            VALUES (?, ?)
            """,
            (memory_id, category)
        )
        conn.commit()


def _memory_add_memory(memory: str):
    """
    Helper function to add a memory entry to the database.

    Args:
        memory (str): The content of the memory to be stored.
    
    Returns:
        str: The unique identifier of the newly created memory entry.
    """
    memory_id = str(uuid.uuid4())
    created_at = datetime.now().isoformat()
    
    with _open_conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO memories (id, memory, created_at) VALUES (?, ?, ?)",
            (memory_id, memory, created_at)
        )
        conn.commit()
    
    return memory_id


def _memory_add(memory: MemoryEntry):
    """
    Adds a new memory entry to the database, along with associated keywords and category.

    Args:
        memory (MemoryEntry): The memory payload to be stored.

    Raises:
        HTTPException: If neither keywords nor category are provided.
        HTTPException: If the provided category is not in the list of allowed categories.
        HTTPException: If there is an error during the database operation.

    Returns:
        dict: A dictionary with the status of the operation and the ID of the newly created memory.
    """
    logger.debug(f"Adding memory: {memory}")
    if not memory.memory:
        logger.debug("Memory content is required.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Memory content is required."
        )

    if not memory.keywords and not memory.category:
        logger.debug("No keywords or category provided.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of keywords or category must be provided."
        )

    try:
        memory_id = _memory_add_memory(memory.memory)

        if not memory_id:
            logger.error("Failed to create memory entry.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create memory entry."
            )

        if memory.keywords:
            _memory_add_keywords(memory_id, memory.keywords)
        
        if memory.category:
            _memory_add_category(memory_id, memory.category)

        logger.debug(f"Memory added with ID: {memory_id}, keywords: {memory.keywords}, category: {memory.category}, memory: {memory.memory}")
        return {"status": "memory created", "id": memory_id}
    except Exception as e:
        logger.error(f"Error adding memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding memory: {str(e)}"
        )