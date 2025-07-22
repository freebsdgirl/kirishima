from shared.models.ledger import MemorySearchParams, MemoryEntry

from app.services.memory.get_details import _get_memory_details
from app.services.memory.util import _memory_exists

from app.util import _open_conn

import sqlite3
from datetime import datetime
from typing import List, Set
from fastapi import HTTPException, status

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")


def _apply_filters(params: MemorySearchParams) -> Set[str]:
    """
    Apply multiple search filters to find memory IDs that match ALL specified criteria.
    
    Args:
        params (MemorySearchParams): Search parameters containing various filter criteria.
    
    Returns:
        Set[str]: Set of memory IDs that match all specified filters.
    """
    with _open_conn() as conn:
        cursor = conn.cursor()
        
        # Start with all memory IDs, then apply filters to narrow down
        cursor.execute("SELECT id FROM memories")
        all_memory_ids = {row[0] for row in cursor.fetchall()}
        
        result_ids = all_memory_ids.copy()
        
        # Apply keyword filter
        if params.keywords and len(params.keywords) > 0:
            keywords_norm = [k.lower() for k in params.keywords]
            q_marks = ','.join('?' for _ in keywords_norm)
            
            # Try progressively lower minimum keyword matches
            current_min_keywords = min(params.min_keywords, len(keywords_norm))
            keyword_matches = set()
            
            while current_min_keywords > 0 and not keyword_matches:
                cursor.execute(f"""
                    SELECT memory_id, COUNT(DISTINCT tag) as match_count
                    FROM memory_tags 
                    WHERE lower(tag) IN ({q_marks})
                    GROUP BY memory_id
                    HAVING COUNT(DISTINCT tag) >= ?
                """, keywords_norm + [current_min_keywords])
                
                keyword_matches = {row[0] for row in cursor.fetchall()}
                if not keyword_matches:
                    current_min_keywords -= 1
            
            logger.debug(f"Keyword filter found {len(keyword_matches)} memories with min_keywords={current_min_keywords}")
            result_ids &= keyword_matches
        
        # Apply category filter
        if params.category:
            cursor.execute("""
                SELECT memory_id FROM memory_category WHERE category = ?
            """, (params.category,))
            category_matches = {row[0] for row in cursor.fetchall()}
            logger.debug(f"Category filter found {len(category_matches)} memories")
            result_ids &= category_matches
        
        # Apply topic filter
        if params.topic_id:
            cursor.execute("""
                SELECT memory_id FROM memory_topics WHERE topic_id = ?
            """, (params.topic_id,))
            topic_matches = {row[0] for row in cursor.fetchall()}
            logger.debug(f"Topic filter found {len(topic_matches)} memories")
            result_ids &= topic_matches
        
        # Apply time filters
        if params.created_after or params.created_before:
            time_conditions = []
            time_params = []
            
            if params.created_after:
                time_conditions.append("created_at >= ?")
                time_params.append(params.created_after)
            
            if params.created_before:
                time_conditions.append("created_at <= ?")
                time_params.append(params.created_before)
            
            time_query = f"SELECT id FROM memories WHERE {' AND '.join(time_conditions)}"
            cursor.execute(time_query, time_params)
            time_matches = {row[0] for row in cursor.fetchall()}
            logger.debug(f"Time filter found {len(time_matches)} memories")
            result_ids &= time_matches
        
        return result_ids


def _update_memory_access_stats(memory_id: str):
    """
    Update access statistics for a memory entry.
    
    Args:
        memory_id (str): The ID of the memory to update.
    """
    with _open_conn() as conn:
        cursor = conn.cursor()
        now_local = datetime.now().isoformat()
        cursor.execute(
            "UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
            (now_local, memory_id)
        )
        conn.commit()


def _memory_search(params: MemorySearchParams) -> List[MemoryEntry]:
    """
    Search memories based on various criteria. Multiple filters can be combined using AND logic.
    
    This function handles memory search with the following behaviors:
    - If memory_id is provided, returns that specific memory (ignoring other filters)
    - Otherwise, applies all specified filters using AND logic (all must match)
    - Supports searching by keywords with minimum match requirement
    - Supports filtering by category, topic, and time ranges
    - Updates access statistics for retrieved memories
    - Handles database query scenarios with robust error handling
    
    Args:
        params (MemorySearchParams): Search parameters containing various filter criteria
    
    Returns:
        List[MemoryEntry]: A list of memory entries matching all specified criteria
    
    Raises:
        HTTPException: For invalid search parameters or database-related errors
    """
    logger.debug(f"Search parameters: {params}")
    
    # Validate parameters
    if params.keywords and len(params.keywords) < params.min_keywords:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At least {params.min_keywords} keywords must be provided."
        )
    
    if params.created_after and params.created_before:
        if params.created_after >= params.created_before:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="created_after must be before created_before."
            )
    
    try:
        # Special case: direct memory ID lookup
        if params.memory_id:
            if not _memory_exists(params.memory_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Memory ID {params.memory_id} not found."
                )
            
            # Use _get_memory_details to get complete information including topic data
            memories = _get_memory_details({params.memory_id})
        else:
            # Combined search using filters
            memory_ids = _apply_filters(params)
            memories = _get_memory_details(memory_ids)
        
        if not memories:
            logger.debug("No memories found for the given search criteria.")
            return []
        
        # Update access statistics for all retrieved memories
        for mem in memories:
            _update_memory_access_stats(mem.id)
        
        logger.debug(f"Found {len(memories)} memories matching search criteria")
        return memories

    except sqlite3.OperationalError as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {e}")
