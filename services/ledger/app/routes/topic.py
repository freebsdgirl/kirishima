"""
FastAPI routes for semantic topic deduplication operations.

This module provides HTTP endpoints for semantic topic deduplication.
All business logic is handled in the services layer.
"""

from fastapi import APIRouter, HTTPException, status, Query

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from app.services.topic.dedup_semantic import _topic_deduplicate_semantic

router = APIRouter()


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
