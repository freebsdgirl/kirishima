"""
This module provides an API endpoint for creating new topics in the ledger service.
It defines a FastAPI router with a POST endpoint at /topics, which accepts a topic name,
generates a unique UUID, records the creation timestamp, and inserts the topic into the database.
The endpoint returns the newly created topic's ID and name, or raises an HTTP 500 error if creation fails.
Functions:
    _create_topic(name: str): Creates a new topic in the database and returns its UUID.
    create_topic(name: str): FastAPI endpoint for creating a topic via HTTP POST.
"""
from fastapi import APIRouter, HTTPException, status, Body
from app.util import _find_or_create_topic
from shared.models.ledger import TopicCreateRequest, TopicResponse
from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

router = APIRouter()


def _create_topic(name: str):
    """
    Find an existing topic by name or create a new one if it doesn't exist.
    
    This function prevents duplicate topics with the same name by first checking
    if a topic with the given name already exists. If found, returns the existing
    topic's ID. If not found, creates a new topic and returns its ID.
    
    Args:
        name (str): The name of the topic to find or create.
    
    Returns:
        str: The UUID of the existing or newly created topic.
    """
    return _find_or_create_topic(name)


@router.post("/topics", response_model=TopicResponse)
def create_topic(request: TopicCreateRequest = Body(...)):
    """
    Create a new topic via the /topics endpoint.

    Creates a topic with the given name and returns its unique identifier.
    Raises an HTTPException if topic creation fails.

    Args:
        request (TopicCreateRequest): The request containing the topic name.

    Returns:
        TopicResponse: A response containing the topic's ID and name.

    Raises:
        HTTPException: If topic creation fails with a 500 Internal Server Error.
    """
    topic_id = _create_topic(request.name)

    if not topic_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create topic."
        )
    
    return TopicResponse(id=topic_id, name=request.name)
    