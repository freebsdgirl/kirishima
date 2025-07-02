import sqlite3
import json
from typing import List

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from fastapi import APIRouter, HTTPException, status, Query

router = APIRouter()

def get_db():
    try:
        with open('/app/config/config.json') as f:
            _config = json.load(f)
        db = _config["db"]["brain"]
        # Try to open a connection to check if DB is accessible
        with sqlite3.connect(db, timeout=1.0) as conn:
            pass
        return db
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=500, detail=f"Configuration error: {e}")
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")

@router.get("/memories/search", response_model=dict)
def memory_search(
    keywords: List[str] = Query(None),
    category: str = Query(None),
    memory_id: str = Query(None),
    min_keywords: int = Query(2, alias="min_keywords")
):
    """
    Search for memories by keywords (tags), by category, or by memory_id. Only one of keywords, category, or memory_id may be provided.
    Args:
        keywords (List[str], optional): List of keywords to search for.
        category (str, optional): category to search for.
        memory_id (str, optional): Memory ID to search for.
        min_keywords (int, optional): Minimum number of matching keywords required. Defaults to 2.
    Returns:
        dict: Status and list of matching memory records.
    """
    # Only one of keywords, topic, or memory_id may be provided
    provided = [x is not None and x != [] for x in [keywords, category, memory_id]]
    logger.debug(f"Search parameters - keywords: {keywords}, category: {category}, memory_id: {memory_id}, min_keywords: {min_keywords}")
    if sum(provided) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide exactly one of keywords, category, or memory_id."
        )
    # At least min_keywords keywords must be provided if using keywords
    if keywords and len(keywords) < min_keywords:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"At least {min_keywords} keywords must be provided."
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
                current_min_keywords = min_keywords
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
                    logger.warning(f"No memories found matching keywords: {keywords_norm} with at least {min_keywords} matches.")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"No memories found matching keywords: {keywords_norm} with at least {min_keywords} matches."
                    )
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