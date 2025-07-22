from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from app.util import _open_conn

from shared.models.ledger import MemoryEntry, MemoryListRequest
from fastapi import HTTPException, status


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
