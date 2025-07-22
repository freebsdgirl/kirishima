from app.services.memory.assign_topic_to_memory import _memory_assign_topic
from app.services.memory.create import _memory_add
from app.services.memory.delete import _memory_delete
from app.services.memory.get_memory_by_topic import _get_memory_by_topic
from app.services.memory.get import _get_memory_by_id, _get_memory_keywords, _get_memory_category, _get_memory_topic, _get_memory
from app.services.memory.get_list import _memory_list
from app.services.memory.patch import _memory_patch
from app.services.memory.scan import _scan_user_messages
from app.services.memory.search import _memory_search
from app.services.memory.util import _memory_exists
from app.services.memory.dedup import _memory_deduplicate
from app.services.memory.dedup_topic_based import _memory_deduplicate_topic_based
from app.services.memory.dedup_semantic import _memory_deduplicate_semantic

from shared.models.ledger import MemoryEntry, MemoryListRequest, MemorySearchParams, MemoryDedupResponse

from typing import List

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from fastapi import APIRouter, HTTPException, status, Query

router = APIRouter()


@router.get("")
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


@router.post("", response_model=dict)
def memory_add(memory: MemoryEntry):
    """
    Adds a new memory entry to the database with associated metadata.

    Parameters:
        memory (MemoryEntry): The memory payload to save.

    Returns:
        The result of the add_memory_db function, typically the newly created memory entry or a status indicator.
    """
    return _memory_add(memory)


@router.patch("/by-id/{memory_id}")
def memory_patch(memory_id: str, memory: MemoryEntry):
    """
    Updates an existing memory record in the database with new information.
    Args:
        memory_id (str): The ID of the memory to update.
        memory (Memory): An object containing updated memory data, including optional fields
            such as keywords, category, and memory content.
    Raises:
        HTTPException: If the memory ID is not provided.
        HTTPException: If none of the fields (keywords, category, memory) are provided for update.
    Returns:
        dict: A dictionary containing the status of the operation and the memory ID.
    """
    # Use the URL parameter as the memory ID
    memory.id = memory_id
    logger.debug(f"PATCH /memories/by-id/{memory_id} Request: memory={memory.memory}, keywords={memory.keywords}, category={memory.category}")

    if not memory_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Memory ID must be provided."
        )
    
    if not _memory_exists(memory_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory ID {memory_id} not found."
        )

    if not memory.keywords and not memory.category and not memory.memory:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of keywords, category, or memory must be provided."
        )
    
    try:
        updated = _memory_patch(memory)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update memory."
            )
        logger.info(f"Memory ID {memory_id} updated successfully.")
    except HTTPException as e:
        logger.error(f"Error updating memory ID {memory_id}: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Internal server error while updating memory ID {memory_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while updating the memory."
        )

    return {"status": "success", "id": memory_id}


@router.patch("/by-id/{memory_id}/topic", response_model=dict)
def assign_topic_to_memory(
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


@router.delete("/by-id/{memory_id}", response_model=dict)
def memory_delete(memory_id: str):
    """
    Deletes a memory entry from the database by its ID.

    Args:
        memory_id (str): The ID of the memory to delete. Provided as a path parameter.

    Returns:
        dict: A dictionary containing the status of the deletion and the ID of the deleted memory.

    Raises:
        HTTPException: 
            - 404 Not Found: If no memory with the specified ID exists.
            - 500 Internal Server Error: If an error occurs during the deletion process.
    """
    logger.debug(f"DELETE /memories/{{id}} Request")

    if not _memory_exists(memory_id):
        logger.error(f"Memory with ID {memory_id} not found.")
        return {"status": "error", "message": "Memory not found."}
    try:
        _memory_delete(memory_id)
        logger.info(f"Memory with ID {memory_id} deleted successfully.")
        return {"status": "success", "deleted_memory_id": memory_id}
    except HTTPException as e:
        logger.error(f"Error deleting memory with ID {memory_id}: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Internal server error while deleting memory with ID {memory_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while deleting the memory."
        )


@router.get("/by-id/{memory_id}", response_model=MemoryEntry)
async def get_memory(memory_id: str):
    """
    Retrieve a memory by its ID, including associated keywords, category, and topic.

    Args:
        memory_id (str): The unique identifier of the memory.

    Returns:
        MemoryEntry: A detailed memory entry including keywords, category, and topic.
    
    Raises:
        HTTPException: If the memory does not exist or if there is an error fetching details.
    """
    logger.debug(f"GET /memories/{memory_id} Request")
    
    try:
        return _get_memory(memory_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error fetching memory {memory_id}: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/by-topic/{topic_id}")
def get_memory_by_topic(topic_id: str):
    memory_ids = _get_memory_by_topic(topic_id)
    memories = [_get_memory_by_id(mem_id) for mem_id in memory_ids]

    if not memories:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No memories found for this topic.")

    for memory in memories:
        memory.keywords = _get_memory_keywords(memory.id)
        memory.category = _get_memory_category(memory.id)
        memory.topic = _get_memory_topic(memory.id)

    return {"status": "success", "memories": [MemoryEntry(**memory.__dict__) for memory in memories]}


@router.post("/_scan", status_code=status.HTTP_200_OK)
async def scan() -> dict:
    """
    Scan user messages to identify topics and extract memories.
    
    This endpoint is designed to be called periodically by a scheduler.
    It processes each user's untagged messages, identifies conversational shifts,
    and extracts relevant memories using an LLM.
    
    Returns:
        dict: A summary of the scan process including successful and error counts.
    
    Raises:
        HTTPException: If there are issues retrieving messages or processing the LLM response.
    """
    try:
        result = await _scan_user_messages()
        return result
    except HTTPException as e:
        logger.error(f"Scan failed: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error during scan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during scan: {e}"
        )

@router.get("/_search", response_model=dict)
def memory_search(
    keywords: List[str] = Query(None, description="List of keywords to search for."),
    category: str = Query(None, description="Category to search for."),
    topic_id: str = Query(None, description="The topic ID to search for."),
    memory_id: str = Query(None, description="Memory ID to search for (ignores other filters if provided)."),
    min_keywords: int = Query(2, description="Minimum number of matching keywords required."),
    created_after: str = Query(None, description="Return memories created after this timestamp (ISO format)."),
    created_before: str = Query(None, description="Return memories created before this timestamp (ISO format).")
):
    """
    FastAPI endpoint for searching memories. Accepts query parameters and converts them
    to a MemorySearchParams model instance for validation and processing.
    
    Multiple parameters can be combined using AND logic (all specified filters must match).
    If memory_id is provided, other filters are ignored and only that specific memory is returned.
    """
    logger.debug(f"Search endpoint called with: keywords={keywords}, memory_id={memory_id}, category={category}")
    
    params = MemorySearchParams(
        keywords=keywords,
        category=category,
        topic_id=topic_id,
        memory_id=memory_id,
        min_keywords=min_keywords,
        created_after=created_after,
        created_before=created_before
    )
    
    logger.debug(f"Created params: {params}")

    try:
        memories = _memory_search(params)

        if not memories:
            logger.debug(f"No memories found for params: {params}")
            return {"status": "ok", "memories": []}

        logger.debug(f"Found {len(memories)} memories")
        return {"status": "ok", "memories": memories}
    except HTTPException as e:
        logger.error(f"HTTPException in search: {e.status_code} - {e.detail}")
        if e.status_code == status.HTTP_404_NOT_FOUND:
            return {"status": "not_found", "detail": e.detail}
        elif e.status_code == status.HTTP_400_BAD_REQUEST:
            return {"status": "bad_request", "detail": e.detail}
        elif e.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
            logger.error(f"Internal server error: {e.detail}")
            return {"status": "error", "detail": e.detail}
        else:
            logger.error(f"Unhandled HTTPException: {e.detail}")
            return {"status": "error", "detail": f"Unhandled HTTP error occurred: {e.detail}"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"status": "error", "detail": f"Unexpected error occurred: {e}"}

@router.get("/_dedup")
async def deduplicate_memories_by_topic(
    dry_run: bool = Query(False, description="If True, only analyze and return what would be done without making changes"),
    grouping_strategy: str = Query("topic_similarity", description="Strategy for grouping memories"),
    min_keyword_matches: int = Query(2, description="Minimum number of matching keywords for keyword_overlap strategy"),
    timeframe_days: int = Query(7, description="Number of days for timeframe grouping window")
):
    """
    Asynchronously deduplicates memories using different grouping strategies.
    
    Grouping strategies:
    - "topic_similarity": Groups memories by semantically similar topics using LLM
    - "keyword_overlap": Groups memories by shared keywords (requires min_keyword_matches)
    - "timeframe": Groups memories created within the same timeframe window
    
    Args:
        dry_run: If True, only analyze and return what would be done without making changes
        grouping_strategy: Strategy for grouping memories ("topic_similarity", "keyword_overlap", "timeframe")
        min_keyword_matches: Minimum number of matching keywords for keyword_overlap strategy
        timeframe_days: Number of days for timeframe grouping window
    
    Returns:
        dict: Results of the deduplication operation or dry run information
        
    Raises:
        HTTPException: 
            - 400 Bad Request: If grouping strategy is invalid
            - 404 Not Found: If no topics/memories are found
            - 500 Internal Server Error: If processing fails
    """
    logger.debug(f"GET /memories/_dedup Request: dry_run={dry_run}, grouping_strategy={grouping_strategy}, min_keyword_matches={min_keyword_matches}, timeframe_days={timeframe_days}")

    # Call service layer with the exact same parameters as the original endpoint
    result = await _memory_deduplicate(
        dry_run=dry_run,
        grouping_strategy=grouping_strategy,
        min_keyword_matches=min_keyword_matches,
        timeframe_days=timeframe_days
    )
    
    logger.debug(f"Deduplication result: {result.get('status', 'unknown')}")
    return result


@router.post("/_dedup_topic_based")
async def deduplicate_memories_topic_based(
    topic_similarity_threshold: float = Query(0.8, description="Semantic similarity threshold for topic grouping (0.7-0.9)"),
    max_topic_groups: int = Query(20, description="Maximum topic groups to consolidate (10-50)"),
    max_memory_chunks: int = Query(50, description="Maximum memory chunks to deduplicate (20-100)"),
    max_memories_per_chunk: int = Query(15, description="Maximum memories per chunk sent to LLM (10-20)"),
    chunk_days: int = Query(7, description="Days per timeframe chunk (3-14)"),
    max_total_tokens: int = Query(100000, description="Maximum total tokens to process (50k-200k)"),
    dry_run: bool = Query(False, description="If true, only analyze and return cost estimates without making changes")
):
    """
    Topic-based memory deduplication with timeframe chunking.
    
    Process:
    1. Find similar topics using semantic similarity
    2. Consolidate similar topics by merging them (reassigning memories first)
    3. Deduplicate memories within consolidated topics by timeframe chunks
    
    Args:
        topic_similarity_threshold: Semantic similarity threshold for topic grouping (0.7-0.9)
        max_topic_groups: Maximum topic groups to consolidate (10-50)
        max_memory_chunks: Maximum memory chunks to deduplicate (20-100)
        max_memories_per_chunk: Maximum memories per chunk sent to LLM (10-20)
        chunk_days: Days per timeframe chunk (3-14)
        max_total_tokens: Maximum total tokens to process (50k-200k)
        dry_run: If true, only analyze and return cost estimates without making changes
    
    Returns:
        dict: Results of the topic-based deduplication operation
        
    Raises:
        HTTPException: 
            - 400 Bad Request: If parameters are invalid
            - 404 Not Found: If no topics with memories are found
            - 501 Not Implemented: If sentence-transformers library is not available
            - 500 Internal Server Error: If processing fails
    """
    logger.debug(f"POST /memories/_dedup_topic_based Request: topic_similarity_threshold={topic_similarity_threshold}, max_topic_groups={max_topic_groups}, max_memory_chunks={max_memory_chunks}, max_memories_per_chunk={max_memories_per_chunk}, chunk_days={chunk_days}, max_total_tokens={max_total_tokens}, dry_run={dry_run}")

    # Validate parameters
    if not 0.0 <= topic_similarity_threshold <= 1.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="topic_similarity_threshold must be between 0.0 and 1.0"
        )
    
    if chunk_days <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="chunk_days must be positive"
        )
    
    if max_memories_per_chunk <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="max_memories_per_chunk must be positive"
        )
    
    if max_topic_groups <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="max_topic_groups must be positive"
        )

    # Call service layer with the exact same parameters as the original endpoint
    result = await _memory_deduplicate_topic_based(
        topic_similarity_threshold=topic_similarity_threshold,
        max_topic_groups=max_topic_groups,
        max_memory_chunks=max_memory_chunks,
        max_memories_per_chunk=max_memories_per_chunk,
        chunk_days=chunk_days,
        max_total_tokens=max_total_tokens,
        dry_run=dry_run
    )
    
    logger.debug(f"Topic-based deduplication result: {result.get('status', 'unknown')}")
    return result


@router.get("/_dedup_semantic", response_model=MemoryDedupResponse)
async def deduplicate_memories_semantic(
    grouping: str = Query("timeframe", description="Grouping strategy: 'timeframe' or 'keyword'"),
    timeframe_days: int = Query(7, description="Days for timeframe grouping"),
    min_shared_keywords: int = Query(2, description="Minimum shared keywords for keyword grouping"),
    dry_run: bool = Query(False, description="If True, only analyze without making changes")
):
    """
    Global memory deduplication using timeframe or keyword grouping.
    
    Args:
        grouping: Grouping strategy ("timeframe" or "keyword")
        timeframe_days: Number of days for timeframe grouping window
        min_shared_keywords: Minimum number of shared keywords for keyword grouping
        dry_run: If True, only analyze and return what would be done without making changes
    
    Returns:
        MemoryDedupResponse: Results of the semantic deduplication operation
        
    Raises:
        HTTPException: 
            - 400 Bad Request: If grouping strategy is invalid
            - 404 Not Found: If no memories are found
            - 500 Internal Server Error: If processing fails
    """
    logger.debug(f"GET /memories/_dedup_semantic Request: grouping={grouping}, timeframe_days={timeframe_days}, min_shared_keywords={min_shared_keywords}, dry_run={dry_run}")

    # Call service layer
    result = await _memory_deduplicate_semantic(
        grouping=grouping,
        timeframe_days=timeframe_days,
        min_shared_keywords=min_shared_keywords,
        dry_run=dry_run
    )
    
    logger.debug(f"Semantic deduplication result: {result.status}")
    return result
