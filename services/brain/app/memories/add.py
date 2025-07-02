"""
This module provides an API endpoint for adding new memories to the memories database.
It defines a FastAPI router with a single POST endpoint `/memories/add` that allows users to save a memory along with associated tags (keywords), category, priority, and user ID. The endpoint validates input, ensures at least one of keywords or category is provided, and inserts the memory and its metadata into the appropriate SQLite database tables. It also checks that the category, if provided, is among the allowed categories.
Modules and Libraries:
- FastAPI for API routing and HTTP exception handling.
- sqlite3 for database operations.
- json for configuration loading.
- uuid for generating unique memory IDs.
- datetime for timestamping.
- shared.log_config for logging.
Endpoint:
- POST `/memories/add`: Adds a new memory with associated tags and category.
Raises:
- HTTP 400 if neither keywords nor category is provided, or if the category is invalid.
- HTTP 500 for database or other internal errors.
"""
from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import sqlite3
import json
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException, status, Query
router = APIRouter()


# note that user_id needs to be provided, but we don't have it implmented in tools yet.
@router.post("/memories/add", response_model=dict)
def memory_add(
    memory: str = Query(None, description="The memory text to save."),
    keywords: list = Query(None, description="List of tags/keywords associated with the memory."),
    category: str = Query(None, description="Category associated with the memory, default is None."),
    priority: float = Query(0.5, description="Priority level for the memory, between 0.0 and 1.0, default is 0.5."),
    user_id: str = Query("c63989a3-756c-4bdf-b0c2-13d01e129e02", description="User ID for the memory, default is a stub user ID for testing.")
):
    """
    Add a new memory and its tags to the memories database.
    Args:
        memory (str): The memory text to save.
        tags (list): List of tags/keywords associated with the memory.
        category (str): The category associated with the memory
        priority (float): Priority level (0.0 to 1.0).
        user_id (str): User ID for the memory, default is a stub user ID for testing.
    Returns:
        str: The ID of the new memory, or an error dict on failure.
    """
    with open('/app/config/config.json') as f:
        _config = json.load(f)
    MEMORIES_DB = _config['db']['memories']

    # verify that both keywords and category are provided
    if not keywords and not category:
        logger.debug("No keywords or category provided.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of keywords or category must be provided."
        )

    memory_id = str(uuid.uuid4())
    # Use local time instead of UTC
    created_at = datetime.now().isoformat()
    try:
        with sqlite3.connect(MEMORIES_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.execute(
                """
                INSERT INTO memories (id, user_id, memory, created_at, priority)
                VALUES (?, ?, ?, ?, ?)
                """,
                (memory_id, user_id, memory, created_at, priority)
            )
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
     
            if category:
                # verify category matches one of the allowed categories
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
                cursor.execute(
                        """
                        INSERT INTO memory_category (memory_id, category)
                        VALUES (?, ?)
                        """,
                        (memory_id, category)
                    )
                conn.commit()
        logger.debug(f"Memory added with ID: {memory_id}, user_id: {user_id}, keywords: {keywords}, category: {category}, priority: {priority}, memory: {memory}")
        return {"status": "memory created", "id": memory_id}
    except Exception as e:
        logger.error(f"Error adding memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error adding memory: {str(e)}"
        )
