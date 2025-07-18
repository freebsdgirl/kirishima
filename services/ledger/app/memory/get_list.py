"""
This module provides an API endpoint and helper function for retrieving a paginated list of memory entries from the ledger database.
Functions:
    _memory_list(request: MemoryListRequest):
        Helper function to fetch memory entries with associated tags and categories, supporting pagination and ordering.
        Raises HTTPException on error.
    memory_list(limit: int, offset: int):
        FastAPI route handler for GET /memories.
        Returns a paginated list of memory entries with tags and categories.
        Validates input parameters and raises HTTPException for errors or empty results.
Dependencies:
    - shared.log_config.get_logger: For logging.
    - app.util._open_conn: For database connection management.
    - shared.models.ledger.MemoryEntry, MemoryListRequest: Data models.
    - fastapi.APIRouter, HTTPException, status, Query: FastAPI components.
"""
from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from app.util import _open_conn

from shared.models.ledger import MemoryEntry, MemoryListRequest
from fastapi import APIRouter, HTTPException, status, Query
router = APIRouter()


def _memory_list(request: MemoryListRequest):
    """
    Helper function to retrieve a list of memories with pagination and ordering.

    Args:
        request (MemoryListRequest): Request object containing pagination and ordering parameters.

    Returns:
        list: A list of dictionaries containing memory details.
    Raises:
        HTTPException: If an error occurs while fetching memories.
    """
    
    try:
        with _open_conn() as conn:
            cursor = conn.cursor()
            # Fetch all memories
            cursor.execute(f"SELECT id, memory, created_at, access_count, last_accessed FROM memories ORDER BY created_at DESC LIMIT ? OFFSET ?", (request.limit, request.offset))
            memories = cursor.fetchall()
            
            # Fetch all tags
            cursor.execute("SELECT memory_id, tag FROM memory_tags")
            tags = cursor.fetchall()
            # Map memory_id to list of tags
            tag_map = {}
            for memory_id, tag in tags:
                tag_map.setdefault(memory_id, []).append(tag)
                
            # Fetch all categories
            cursor.execute("SELECT memory_id, category FROM memory_category")
            categories = cursor.fetchall()
            # Map memory_id to list of categories
            category_map = {}
            for memory_id, category in categories:
                category_map[memory_id] = category  # Store single category, not list
                
            # Fetch all topic associations
            cursor.execute("SELECT memory_id, topic_id FROM memory_topics")
            topic_associations = cursor.fetchall()
            # Map memory_id to topic_id
            topic_map = {}
            for memory_id, topic_id in topic_associations:
                topic_map[memory_id] = topic_id
                
            # Fetch all topic names for efficient lookup
            cursor.execute("SELECT id, name FROM topics")
            topic_names = cursor.fetchall()
            topic_name_map = {}
            for topic_id, topic_name in topic_names:
                topic_name_map[topic_id] = topic_name
            
            # Build result list
            result = []
            for row in memories:
                mem_id = row[0]
                topic_id = topic_map.get(mem_id)
                topic_name = topic_name_map.get(topic_id) if topic_id else None
                
                result.append(
                    MemoryEntry(
                        id=mem_id,
                        memory=row[1],
                        created_at=row[2],
                        access_count=row[3],
                        last_accessed=row[4],
                        keywords=tag_map.get(mem_id, []),
                        category=category_map.get(mem_id),  # Single category
                        topic_id=topic_id,
                        topic_name=topic_name
                    )
                )
        logger.debug(f"Fetched {len(result)} memories with limit={request.limit} and offset={request.offset}")
        return result
    except Exception as e:
        logger.error(f"Error fetching memories: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching memories: {str(e)}"
        )

@router.get("/memories")
def memory_list(
    limit: int = Query(10, description="Maximum number of memories to return."),
    offset: int = Query(0, description="Offset for pagination, default is 0.")
):
    """
    List all memories with pagination support.

    Args:
        limit (int): Maximum number of memories to return. Default is 10.
        offset (int): Offset for pagination. Default is 0.
        order_by (str): Column to order results by. Default is 'created_at'.

    Returns:
        dict: A dictionary containing the status and a list of memory records.
    
    Raises:
        HTTPException: 
            - 500 Internal Server Error: If an error occurs while fetching memories.
    """
    logger.debug(f"GET /memories Request: limit={limit}, offset={offset}")

    if limit <= 0 or offset < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid parameters: limit must be greater than 0 and offset must be non-negative."
        )
    
    request = MemoryListRequest(limit=limit, offset=offset)
    memories = _memory_list(request)

    if not memories:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No memories found."
        )

    return {"status": "success", "memories": memories}