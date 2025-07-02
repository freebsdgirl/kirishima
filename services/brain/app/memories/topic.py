"""
This module provides an API endpoint for assigning a topic to a memory in the database.
Endpoints:
    PATCH /memories/topic:
        Assigns a topic to a memory by inserting a record into the `memory_topics` table.
        - Parameters:
            - memory_id (str): The ID of the memory to assign the topic to.
            - topic_id (str): The ID of the topic to assign.
        - Returns:
            - dict: Status message indicating success or failure.
        - Raises:
            - HTTPException 400: If memory_id or topic_id is not provided.
            - HTTPException 500: If a database or unexpected error occurs.
Dependencies:
    - FastAPI for API routing and exception handling.
    - sqlite3 for database operations.
    - json for configuration loading.
    - shared.log_config for logging.
"""
from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import sqlite3
import json

from fastapi import APIRouter, HTTPException, status, Query
router = APIRouter()


@router.patch("/memories/topic", response_model=dict)
def memory_topic(
    memory_id: str = Query(..., description="The ID of the memory to assign the topic to."),
    topic_id: str = Query(..., description="The ID of the topic to assign.")
):
    """
    Assign a topic to a memory.

    Args:
        memory_id (str): The ID of the memory to assign the topic to.
        topic_id (str): The ID of the topic to assign.

    Returns:
        dict: Status message indicating success or failure.
    
    Raises:
        HTTPException: 
            - 400 Bad Request: If memory_id or topic_id is not provided.
            - 500 Internal Server Error: If an error occurs while assigning the topic.
    """
    logger.debug(f"PATCH /memories/topic Request: memory_id={memory_id}, topic_id={topic_id}")

    if not memory_id or not topic_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Both memory_id and topic_id must be provided."
        )

    try:
        with open('/app/config/config.json') as f:
            _config = json.load(f)
        MEMORIES_DB = _config['db']['memories']

        with sqlite3.connect(MEMORIES_DB) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO memory_topics (memory_id, topic_id) VALUES (?, ?)",
                (memory_id, topic_id)
            )
            conn.commit()

        return {"status": "ok", "message": f"Topic {topic_id} assigned to memory {memory_id}."}

    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )