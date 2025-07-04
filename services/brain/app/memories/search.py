"""
This module provides an API endpoint for searching memory records in a SQLite database.
It allows searching by keywords (tags), category, topic ID, or memory ID, but only one search criterion may be used per request.
The endpoint supports filtering by a minimum number of matching keywords and returns detailed memory information for matching records.
It also updates access statistics for each accessed memory.

Functions:
    memory_search(keywords: List[str], category: str, topic_id: str, memory_id: str, min_keywords: int) -> dict:
        FastAPI route handler for searching memories by keywords, category, topic ID, or memory ID.
        Returns a dictionary with the search status and a list of matching memory records.
"""

import sqlite3
import json
from typing import List

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from fastapi import APIRouter, HTTPException, status, Query

router = APIRouter()


@router.get("/memories/search", response_model=dict)
def memory_search(
    keywords: List[str] = Query(None, description="List of keywords to search for."),
    category: str = Query(None, description="Category to search for."),
    topic_id: str = Query(None, description="The topic ID to search for."),
    memory_id: str = Query(None, description="Memory ID to search for."),
    min_keywords: int = Query(2, description="Minimum number of matching keywords required.")
):
    """
    Search for memories by keywords (tags), by category, or by memory_id. Only one of keywords, category, or memory_id may be provided.
    Args:
        keywords (List[str], optional): List of keywords to search for.
        category (str, optional): category to search for.
        topic_id (str, optional): The topic ID to search for.
        memory_id (str, optional): Memory ID to search for.
        min_keywords (int, optional): Minimum number of matching keywords required. Defaults to 2.
    Returns:
        dict: Status and list of matching memory records.
    """
    # Only one of keywords, topic, or memory_id may be provided
    provided = [
        (keywords is not None and isinstance(keywords, list) and len(keywords) > 0),
        (category is not None and isinstance(category, str) and category != ""),
        (topic_id is not None and isinstance(topic_id, str) and topic_id != ""),
        (memory_id is not None and isinstance(memory_id, str) and memory_id != "")
    ]
    logger.debug(f"Search parameters - keywords: {keywords}, category: {category}, topic_id: {topic_id}, memory_id: {memory_id}, min_keywords: {min_keywords}, provided: {provided}")
    if sum(provided) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide exactly one of keywords, category, topic_id, or memory_id."
        )
    # At least min_keywords keywords must be provided if using keywords
    # FastAPI will always pass min_keywords as an int, but if running outside FastAPI, ensure it's an int
    if keywords is not None and isinstance(keywords, list):
        try:
            min_keywords_int = int(min_keywords)
        except Exception:
            min_keywords_int = 2
        if len(keywords) < min_keywords_int:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"At least {min_keywords_int} keywords must be provided."
            )
    try:
        with open('/app/config/config.json') as f:
            _config = json.load(f)
        MEMORIES_DB = _config['db']['memories']
        with sqlite3.connect(MEMORIES_DB) as conn:
            cursor = conn.cursor()
            if keywords:
                # Normalize keywords to lowercase
                keywords_norm = [k.lower() for k in keywords]
                q_marks = ','.join('?' for _ in keywords_norm)
                try:
                    min_keywords_int = int(min_keywords)
                except Exception:
                    min_keywords_int = 2
                current_min_keywords = min_keywords_int
                while current_min_keywords > 0:
                    cursor.execute(f"""
                        SELECT m.id, m.created_at, m.priority, COUNT(mt.tag) as match_count
                        FROM memories m
                        JOIN memory_tags mt ON m.id = mt.memory_id
                        WHERE lower(mt.tag) IN ({q_marks})
                        GROUP BY m.id
                        HAVING COUNT(mt.tag) >= ?
                        ORDER BY match_count DESC, m.priority DESC, m.created_at DESC
                    """, keywords_norm + [current_min_keywords])
                    rows = cursor.fetchall()
                    logger.debug(f"Found {len(rows)} memories matching keywords: {keywords_norm} with min_keywords={current_min_keywords}")
                    if rows:
                        break
                    current_min_keywords -= 1
                if not rows:
                    return {"status": "ok", "memories": []}
                memory_ids = [row[0] for row in rows]
            elif category:
                cursor.execute("""
                    SELECT m.id, m.created_at, m.priority
                    FROM memories m
                    JOIN memory_category mt ON m.id = mt.memory_id
                    WHERE mt.category = ?
                    ORDER BY m.created_at DESC
                """, (category,))
                rows = cursor.fetchall()
                logger.debug(f"Found {len(rows)} memories matching category: {category}")
                memory_ids = [row[0] for row in rows]
            elif topic_id:
                # get the memory ids from memory_topics
                cursor.execute("SELECT memory_id FROM memory_topics WHERE topic_id = ?", (topic_id,))
                memory_ids = [row[0] for row in cursor.fetchall()]
                logger.debug(f"Found {len(memory_ids)} memories for topic_id: {topic_id}")
                if not memory_ids:
                    logger.warning(f"No memories found for topic_id: {topic_id}")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"No memories found for topic_id: {topic_id}"
                    )
                # Fetch all memory records for the found IDs
                q_marks_mem = ','.join('?' for _ in memory_ids)
                cursor.execute(f"SELECT id, user_id, memory, created_at, access_count, last_accessed, priority FROM memories WHERE id IN ({q_marks_mem})", memory_ids)
                memories = [
                    {
                        "id": row[0],
                        "user_id": row[1],
                        "memory": row[2],
                        "created_at": row[3],
                        "access_count": row[4],
                        "last_accessed": row[5],
                        "priority": row[6],
                    }
                    for row in cursor.fetchall()
                ]
            else:  # memory_id
                cursor.execute("SELECT id, user_id, memory, created_at, access_count, last_accessed, priority FROM memories WHERE id = ?", (memory_id,))
                row = cursor.fetchone()
                logger.debug(f"Searching for memory_id: {memory_id}, found: {row is not None}")
                if not row:
                    # return HTTP 404 if memory_id not found
                    logger.error(f"Memory ID {memory_id} not found")
                    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Memory ID {memory_id} not found")
                memories = [{
                    "id": row[0],
                    "user_id": row[1],
                    "memory": row[2],
                    "created_at": row[3],
                    "access_count": row[4],
                    "last_accessed": row[5],
                    "priority": row[6],
                }]
                # Update access_count and last_accessed for this memory
                from datetime import datetime
                now_local = datetime.now().isoformat()
                cursor.execute(
                    "UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                    (now_local, memory_id)
                )
                conn.commit()
                return {"status": "ok", "memories": memories}
            if not memory_ids:
                return {"status": "ok", "memories": []}
            # Fetch all memory records for the found IDs
            q_marks_mem = ','.join('?' for _ in memory_ids)
            cursor.execute(f"SELECT id, user_id, memory, created_at, access_count, last_accessed, priority FROM memories WHERE id IN ({q_marks_mem})", memory_ids)
            memories = [
                {
                    "id": row[0],
                    "user_id": row[1],
                    "memory": row[2],
                    "created_at": row[3],
                    "access_count": row[4],
                    "last_accessed": row[5],
                    "priority": row[6],
                }
                for row in cursor.fetchall()
            ]
            # After collecting memories, update access_count and last_accessed for each
            from datetime import datetime
            now_local = datetime.now().isoformat()
            for mem in memories:
                cursor.execute(
                    "UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
                    (now_local, mem["id"])
                )
            conn.commit()
        return {"status": "ok", "memories": memories}
    except sqlite3.OperationalError as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {e}")