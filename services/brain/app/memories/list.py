"""
This module provides an API endpoint for listing memory records with pagination support.
It defines a FastAPI router with a single GET endpoint `/memories` that retrieves memory entries from a SQLite database.
Each memory entry includes its associated tags (keywords) and categories. The endpoint supports pagination via `limit`
and `offset` query parameters. Configuration for the database path is loaded from a JSON config file.
Functions:
    memory_list(limit: int, offset: int) -> dict:
        Lists memory records with their tags and categories, supporting pagination.
"""
from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import sqlite3
import json

from fastapi import APIRouter, HTTPException, status, Query
router = APIRouter()

@router.get("/memories", response_model=dict)
def memory_list(
    limit: int = Query(10, description="Maximum number of memories to return."),
    offset: int = Query(0, description="Offset for pagination, default is 0.")
):
    """
    List all memories with pagination support.

    Args:
        limit (int): Maximum number of memories to return. Default is 10.
        offset (int): Offset for pagination. Default is 0.

    Returns:
        dict: A dictionary containing the status and a list of memory records.
    
    Raises:
        HTTPException: 
            - 500 Internal Server Error: If an error occurs while fetching memories.
    """
    logger.debug(f"GET /memories Request: limit={limit}, offset={offset}")
    
    try:
        with open('/app/config/config.json') as f:
            _config = json.load(f)
        MEMORIES_DB = _config['db']['memories']
        
        with sqlite3.connect(MEMORIES_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            # Fetch all memories
            cursor.execute("SELECT id, user_id, memory, created_at, access_count, last_accessed, priority FROM memories LIMIT ? OFFSET ?", (limit, offset))
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
                category_map.setdefault(memory_id, []).append(category)
            # Build result list
            result = []
            for row in memories:
                mem_id = row[0]
                result.append({
                    "id": mem_id,
                    "memory": row[2],
                    "created_at": row[3],
                    "keywords": tag_map.get(mem_id, []),
                    "categories": category_map.get(mem_id, [])
                })
        logger.debug(f"Fetched {len(result)} memories with limit={limit} and offset={offset}")
        return {"status": "ok", "memories": result}
    except Exception as e:
        logger.error(f"Error fetching memories: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching memories: {str(e)}"
        )