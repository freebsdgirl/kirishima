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
import os
import httpx

from fastapi import APIRouter, HTTPException, status, Query
router = APIRouter()

@router.get("/memories")
def memory_list(
    limit: int = Query(10, description="Maximum number of memories to return."),
    offset: int = Query(0, description="Offset for pagination, default is 0."),
    order_by: str = Query("created_at", description="Column to order results by. Default is 'created_at'.")
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
    logger.debug(f"GET /memories Request: limit={limit}, offset={offset}, order_by={order_by}")
    allowed_columns = {"id", "user_id", "memory", "created_at", "access_count", "last_accessed", "priority"}
    if order_by not in allowed_columns:
        raise HTTPException(status_code=400, detail=f"Invalid order_by column: {order_by}")
    try:
        with open('/app/config/config.json') as f:
            _config = json.load(f)
        MEMORIES_DB = _config['db']['memories']
        
        with sqlite3.connect(MEMORIES_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            # Fetch all memories
            cursor.execute(f"SELECT id, user_id, memory, created_at, access_count, last_accessed, priority FROM memories ORDER BY {order_by} DESC LIMIT ? OFFSET ?", (limit, offset))
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
                    "access_count": row[4],
                    "last_accessed": row[5],
                    "priority": row[6],
                    "user_id": row[1],
                    "keywords": tag_map.get(mem_id, []),
                    "categories": category_map.get(mem_id, [])
                })
        logger.debug(f"Fetched {len(result)} memories with limit={limit} and offset={offset}")
        return result
    except Exception as e:
        logger.error(f"Error fetching memories: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching memories: {str(e)}"
        )


@router.get("/memories/count")
def memory_count():
    """
    Count the total number of memories in the database.

    Returns:
        dict: A dictionary containing the total count of memories.
    
    Raises:
        HTTPException: 
            - 500 Internal Server Error: If an error occurs while counting memories.
    """
    logger.debug("GET /memories/count Request")
    
    try:
        with open('/app/config/config.json') as f:
            _config = json.load(f)
        MEMORIES_DB = _config['db']['memories']
        
        with sqlite3.connect(MEMORIES_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM memories")
            count = cursor.fetchone()[0]
        
        logger.debug(f"Total memories count: {count}")
        return count
    except Exception as e:
        logger.error(f"Error counting memories: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error counting memories: {str(e)}"
        )


@router.get("/memories/id/{memory_id}")
async def memory_get(memory_id: str):
    """
    Get a specific memory by its ID.

    Args:
        memory_id (str): The ID of the memory to retrieve.

    Returns:
        dict: A dictionary containing the memory details, including keywords and categories.
    
    Raises:
        HTTPException: 
            - 404 Not Found: If the memory with the specified ID does not exist.
            - 500 Internal Server Error: If an error occurs while fetching the memory.
    """
    logger.debug(f"GET /memories/{memory_id} Request")
    
    try:
        with open('/app/config/config.json') as f:
            _config = json.load(f)
        MEMORIES_DB = _config['db']['memories']
        
        with sqlite3.connect(MEMORIES_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            # Fetch memory details
            cursor.execute("SELECT id, user_id, memory, created_at, access_count, last_accessed, priority FROM memories WHERE id = ?", (memory_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Memory not found."
                )
            # Fetch tags
            cursor.execute("SELECT tag FROM memory_tags WHERE memory_id = ?", (memory_id,))
            tags = [tag[0] for tag in cursor.fetchall()]
            # Fetch categories
            cursor.execute("SELECT category FROM memory_category WHERE memory_id = ?", (memory_id,))
            category = cursor.fetchone()
            category = category[0] if category else None
        
            # get topic
            cursor.execute("SELECT topic_id FROM memory_topics WHERE memory_id = ?", (memory_id,))
            topic_row = cursor.fetchone()
            if topic_row:
                # resolve the topic id to a name
                topic_id = topic_row[0]

                ledger_port = os.getenv("LEDGER_PORT", 4203)
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.get(f"http://ledger:{ledger_port}/topics/id/{topic_id}")
                        response.raise_for_status()
                        topic_data = response.json()
                        topic_name = topic_data.get("name", "Unknown Topic")
                except httpx.HTTPStatusError as e:
                    logger.error(f"Error fetching topic {topic_id}: {str(e)}")
                    topic_name = "Unknown Topic"
            else:
                topic_name = "No Topic Assigned"


        result = {
            "id": row[0],
            "user_id": row[1],
            "memory": row[2],
            "created_at": row[3],
            "access_count": row[4],
            "last_accessed": row[5],
            "priority": row[6],
            "keywords": tags,
            "category": category,
            "topic": topic_name 
        }
        logger.debug(f"Fetched memory: {result}")
        return result
    except Exception as e:
        logger.error(f"Error fetching memory {memory_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching memory: {str(e)}"
        )