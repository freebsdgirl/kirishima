"""
This module provides search functionality for memory entries in a ledger application using FastAPI and SQLite.
It exposes an API endpoint for searching memories based on various criteria, including keywords, category, topic ID, 
memory ID, and time ranges. Multiple search parameters can be combined using AND logic (all must match).

Key Components:
- `_get_memory_details`: Retrieves complete memory details including content, access stats, keywords, and category.
- `_apply_filters`: Applies multiple search filters to a base query using AND logic.
- `_memory_search`: Main logic for validating search parameters and executing combined queries.
- `memory_search`: FastAPI endpoint for memory search, returning results in a standardized response format.

Models:
- `MemorySearchParams`: Defines the search parameters supporting multiple combined filters.
- `MemoryEntry`: Represents a memory entry with complete data.

Logging:
- Uses a shared logger for debug and error reporting.

Exceptions:
- Raises HTTPException for invalid parameters, not found errors, and database issues.

Usage:
- Import and include the router in your FastAPI application to enable memory search functionality.
"""

import sqlite3
from datetime import datetime
from typing import List, Set
from fastapi import APIRouter, HTTPException, status, Query
from shared.models.ledger import MemorySearchParams, MemoryEntry
from app.util import _open_conn
from app.memory.util import memory_exists
from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

router = APIRouter()


def _get_memory_details(memory_ids: Set[str]) -> List[MemoryEntry]:
    """
    Retrieve complete memory details for a set of memory IDs.
    
    Args:
        memory_ids (Set[str]): Set of memory IDs to retrieve details for.
    
    Returns:
        List[MemoryEntry]: A list of complete memory entries.
    """
    if not memory_ids:
        return []
    
    with _open_conn() as conn:
        cursor = conn.cursor()
        placeholders = ','.join('?' for _ in memory_ids)
        
        # Get basic memory data
        cursor.execute(f"""
            SELECT id, memory, created_at, access_count, last_accessed
            FROM memories 
            WHERE id IN ({placeholders})
            ORDER BY created_at DESC
        """, list(memory_ids))
        
        memories = cursor.fetchall()
        
        # Get keywords for all memories
        cursor.execute(f"""
            SELECT memory_id, tag 
            FROM memory_tags 
            WHERE memory_id IN ({placeholders})
        """, list(memory_ids))
        
        keyword_map = {}
        for memory_id, tag in cursor.fetchall():
            keyword_map.setdefault(memory_id, []).append(tag)
        
        # Get categories for all memories
        cursor.execute(f"""
            SELECT memory_id, category 
            FROM memory_category 
            WHERE memory_id IN ({placeholders})
        """, list(memory_ids))
        
        category_map = {}
        for memory_id, category in cursor.fetchall():
            category_map[memory_id] = category
        
        # Get topic associations for all memories
        cursor.execute(f"""
            SELECT memory_id, topic_id 
            FROM memory_topics 
            WHERE memory_id IN ({placeholders})
        """, list(memory_ids))
        
        topic_map = {}
        for memory_id, topic_id in cursor.fetchall():
            topic_map[memory_id] = topic_id
        
        # Get topic names for efficient lookup
        if topic_map:
            topic_ids = list(set(topic_map.values()))
            topic_placeholders = ','.join('?' for _ in topic_ids)
            cursor.execute(f"""
                SELECT id, name 
                FROM topics 
                WHERE id IN ({topic_placeholders})
            """, topic_ids)
            
            topic_name_map = {}
            for topic_id, topic_name in cursor.fetchall():
                topic_name_map[topic_id] = topic_name
        else:
            topic_name_map = {}
        
        # Build complete memory entries
        result = []
        for row in memories:
            memory_id = row[0]
            topic_id = topic_map.get(memory_id)
            topic_name = topic_name_map.get(topic_id) if topic_id else None
            
            result.append(MemoryEntry(
                id=memory_id,
                memory=row[1],
                created_at=row[2],
                access_count=row[3] or 0,
                last_accessed=row[4],
                keywords=keyword_map.get(memory_id, []),
                category=category_map.get(memory_id),
                topic_id=topic_id,
                topic_name=topic_name
            ))
        
        return result


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
            if not memory_exists(params.memory_id):
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


@router.get("/memories/_search", response_model=dict)
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
