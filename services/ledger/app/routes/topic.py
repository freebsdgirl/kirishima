"""
Routes for topic management in the ledger service.
This module defines the FastAPI routes for creating, retrieving, updating, deleting, and deduplicating topics,
as well as assigning topics to messages and querying topics by various criteria.
Routes:
    - GET    /topics: Retrieve all topics.
    - POST   /topics: Create a new topic.
    - PATCH  /topics/{topic_id}: Assign a topic to user messages within a specified timestamp range.
    - GET    /topics/{topic_id}: Retrieve a topic by its ID.
    - DELETE /topics/{topic_id}: Delete a topic by its ID.
    - GET    /topics/{topic_id}/messages: Retrieve all user messages associated with a given topic ID.
    - POST   /topics/_by-timeframe: Retrieve topic IDs within a specified time frame.
    - GET    /topics/_recent: Retrieve a list of recent topics.
    - POST   /topics/_dedup_semantic: Perform semantic deduplication of topics using sentence-transformers and clustering.
Each route validates input, handles errors, and delegates business logic to the corresponding service layer functions.
Dependencies:
    - shared.models.ledger: Data models for requests and responses.
    - shared.log_config: Logger configuration.
    - app.services.topic.*: Service layer implementations for topic operations.
    - fastapi: Web framework for route definitions.
    - HTTPException: For various error conditions such as not found, bad request, or internal server errors.
"""

from shared.models.ledger import (
    TopicCreateRequest, 
    TopicResponse, 
    TopicDeleteRequest, 
    CanonicalUserMessage, 
    TopicMessagesRequest, 
    TopicRecentRequest, 
    TopicByIdRequest, 
    TopicIDsTimeframeRequest,
    AssignTopicRequest
)

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from app.services.topic.assign_messages import _assign_messages_to_topic
from app.services.topic.create import _create_topic
from app.services.topic.delete import _delete_topic
from app.services.topic.dedup_semantic import _topic_deduplicate_semantic
from app.services.topic.get_all import _get_all_topics
from app.services.topic.get_id import _get_topic_by_id
from app.services.topic.get_ids_in_timeframe import _get_topic_ids_in_timeframe
from app.services.topic.get_messages import _get_topic_messages
from app.services.topic.get_recent import _get_recent_topics
from app.services.topic.util import _topic_exists, _validate_timestamp

from typing import List

from fastapi import APIRouter, HTTPException, status, Query, Body
router = APIRouter()


@router.get("", response_model=List[TopicResponse])
def get_all_topics():
    """
    Retrieve all topics from the database.

    Returns:
        List[TopicResponse]: A list of topic response objects, each containing the 'id' and 'name' of a topic,
        ordered alphabetically by name.
    """
    return _get_all_topics()


@router.post("", response_model=TopicResponse)
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
    topic_id = _create_topic(request)

    if not topic_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create topic."
        )

    return TopicResponse(id=topic_id, name=request.name)


@router.patch("/{topic_id}")
def assign_topic_to_messages(body: AssignTopicRequest):
    """
    FastAPI route handler for assigning a topic to user messages within a specified timestamp range.
    """
    return _assign_messages_to_topic(body)


@router.get("/{topic_id}", response_model=TopicResponse)
def get_topic_by_id(topic_id: str):
    """
    Retrieve a specific topic by its unique identifier.
    
    This function checks if the specified topic exists, and if so, retrieves the topic details
    using the provided topic ID. It raises a 404 Not Found error if the topic does not exist.
    
    Args:
        topic_id (str): The unique identifier of the topic to retrieve.
    
    Returns:
        TopicResponse: The details of the requested topic.
    
    Raises:
        HTTPException: If the topic does not exist (404 Not Found).
    """
    if not _topic_exists(topic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")
    request = TopicByIdRequest(topic_id=topic_id)
    return _get_topic_by_id(request)


@router.delete("/{topic_id}")
def delete_topic(topic_id: str):
    """
    Delete a specific topic by its unique identifier.
    
    This function checks if the specified topic exists, and if so, attempts to delete the topic
    using the provided topic ID. It raises a 404 Not Found error if the topic does not exist
    or cannot be deleted.
    
    Args:
        topic_id (str): The unique identifier of the topic to delete.
    
    Returns:
        dict: A dictionary containing the number of deleted topics.
    
    Raises:
        HTTPException: If the topic does not exist or cannot be deleted (404 Not Found).
    """
    if not _topic_exists(topic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")
    request = TopicDeleteRequest(topic_id=topic_id)
    deleted_count = _delete_topic(request)
    if deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found or already deleted.")
    return {"deleted": deleted_count}


@router.get("/{topic_id}/messages", response_model=List[CanonicalUserMessage])
def get_messages_by_topic(topic_id: str) -> List[CanonicalUserMessage]:
    """
    Retrieve all user messages associated with a given topic ID.

    This function checks if the specified topic exists, then queries the database for all messages
    related to the topic, ordered by their ID. It parses the 'tool_calls' field from JSON if necessary,
    constructs CanonicalUserMessage objects, and filters out messages with the role 'tool' as well as
    assistant messages with empty content.

    Args:
        topic_id (str): The unique identifier of the topic.

    Returns:
        List[CanonicalUserMessage]: A list of user messages for the topic, excluding tool messages and
        assistant messages with empty content.

    Raises:
        HTTPException: If the topic does not exist (404 Not Found).
    """
    if not _topic_exists(topic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")
    request = TopicMessagesRequest(topic_id=topic_id)
    return _get_topic_messages(request)


@router.post("/_by-timeframe", response_model=List[str])
def get_topic_ids_in_timeframe(body: TopicIDsTimeframeRequest):
    """
    API endpoint to retrieve topic IDs within a specified time frame.

    Args:
        body (TopicIDsTimeframeRequest): Request body containing 'start' and 'end' timestamps.

    Returns:
        List[str]: A list of topic IDs that have messages within the specified time frame.
    """

    if body.start >= body.end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start time must be before end time.")
    if not body.start or not body.end:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Start and end times must be provided.")
    if not _validate_timestamp(body.start) or not _validate_timestamp(body.end):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid timestamp format. Use ISO 8601 format.")
    topic_ids = _get_topic_ids_in_timeframe(body)
    if not topic_ids:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No topics found in the specified time frame.")
    return topic_ids


@router.get("/_recent", response_model=List[TopicResponse])
def get_recent_topics(
    limit: int = Query(5, description="Number of recent topics to return (ordered by recency)"),
):
    """
    Retrieve a list of recent topics.

    Args:
        limit (int, optional): Number of recent topics to return. Defaults to 5.

    Returns:
        List[TopicResponse]: A list of topic response objects, each containing the 'id' and 'name' of a recent topic.

    Notes:
        - Topics are determined from the 'user_messages' table, ordered by 'created_at' in descending order.
        - Only distinct, non-null topic IDs are considered.
    """
    request = TopicRecentRequest(limit=limit)
    return _get_recent_topics(request)


@router.post("/_dedup_semantic")
async def deduplicate_topics_semantic(
    similarity_threshold: float = Query(0.8, description="Cosine similarity threshold for topic grouping (0.7-0.9)"),
    max_clusters: int = Query(10, description="Maximum number of topic clusters to process (5-20)"),
    dry_run: bool = Query(False, description="If true, only analyze and return what would be done without making changes")
):
    """
    Semantic topic deduplication using sentence-transformers and DBSCAN clustering.
    
    Process:
    1. Get all topics with their memory counts
    2. Generate embeddings for topic names using sentence-transformers
    3. Use DBSCAN clustering to find similar topics based on cosine similarity
    4. For each cluster, use LLM to determine the best consolidated topic name
    5. Reassign memories from secondary topics to the primary topic
    6. Delete empty secondary topics
    
    This helps reduce topic fragmentation by consolidating semantically similar topics.
    
    Args:
        similarity_threshold: Cosine similarity threshold for topic grouping (0.7-0.9)
        max_clusters: Maximum number of topic clusters to process (5-20)
        dry_run: If True, only analyze and return what would be done without making changes
    
    Returns:
        dict: Results of the semantic topic deduplication operation
        
    Raises:
        HTTPException: 
            - 400 Bad Request: If parameters are invalid
            - 404 Not Found: If no topics with memories are found
            - 501 Not Implemented: If sentence-transformers library is not available
            - 500 Internal Server Error: If processing fails
    """
    logger.debug(f"POST /topics/_dedup_semantic Request: similarity_threshold={similarity_threshold}, max_clusters={max_clusters}, dry_run={dry_run}")

    # Validate parameters
    if not 0.0 <= similarity_threshold <= 1.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="similarity_threshold must be between 0.0 and 1.0"
        )
    
    if max_clusters <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="max_clusters must be positive"
        )

    # Call service layer
    result = await _topic_deduplicate_semantic(
        similarity_threshold=similarity_threshold,
        max_clusters=max_clusters,
        dry_run=dry_run
    )
    
    logger.debug(f"Semantic topic deduplication result: {result.get('status', 'unknown')}")
    return result
