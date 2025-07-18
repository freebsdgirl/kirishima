"""
This module provides functionality to assign a topic to a memory by inserting a record into the `memory_topics` table.
It exposes a FastAPI PATCH endpoint `/memories/topic` that allows clients to associate a topic with a memory, given their respective IDs.
The module ensures that both the memory and topic exist before performing the assignment, and handles errors gracefully with appropriate HTTP responses.
Functions:
    _memory_assign_topic(memory_id: str, topic_id: str):
        Assigns a topic to a memory in the database after validating their existence.
API Endpoints:
    PATCH /memories/topic:
        Assigns a topic to a memory. Requires `memory_id` and `topic_id` as query parameters.
        Returns a status message upon successful assignment.

"""
from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from app.util import _open_conn
from app.memory.util import memory_exists
from app.topic.util import topic_exists

from fastapi import APIRouter, HTTPException, status, Query
router = APIRouter()


def _memory_assign_topic(memory_id: str, topic_id: str):
    """
    Assign a topic to a memory by inserting a record into the `memory_topics` table.
    
    Args:
        memory_id (str): The ID of the memory to assign the topic to.
        topic_id (str): The ID of the topic to assign.

    Raises:
        HTTPException: If the memory or topic does not exist, or if an error occurs during the database operation.
    """
    if not memory_exists(memory_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Memory not found.")
    
    if not topic_exists(topic_id):
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

@router.patch("/memories/by-id/{memory_id}/topic", response_model=dict)
def memory_topic(
    memory_id: str,
    topic_id: str = Query(..., description="The ID of the topic to assign.")
):
    """
    Assign a topic to a memory by inserting a record into the `memory_topics` table.

    Args:
        memory_id (str): The ID of the memory to assign the topic to.
        topic_id (str): The ID of the topic to assign.

    Returns:
        dict: A dictionary containing the status of the operation.

    Raises:
        HTTPException: If memory_id or topic_id is not provided, or if an error occurs.
    """
    logger.debug(f"PATCH /memories/topic Request with memory_id={memory_id}, topic_id={topic_id}")

    if not memory_id or not topic_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Both memory_id and topic_id must be provided.")

    _memory_assign_topic(memory_id, topic_id)
    
    return {"status": "success", "message": f"Topic {topic_id} assigned to memory {memory_id}."}