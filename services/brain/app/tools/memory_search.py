import sqlite3
import json
from pathlib import Path
from typing import List

def memory_search(keywords: List[str]):
    """
    Search for memories that have tags exactly matching any of the provided keywords (case-insensitive).
    Args:
        keywords (List[str]): List of keywords to search for.
    Returns:
        dict: Status and list of matching memory IDs.
    """
    try:
        with open('/app/config/config.json') as f:
            _config = json.load(f)
        MEMORIES_DB = _config['db']['memories']
        # Normalize keywords to lowercase
        keywords_norm = [k.lower() for k in keywords]
        with sqlite3.connect(MEMORIES_DB) as conn:
            cursor = conn.cursor()
            q_marks = ','.join('?' for _ in keywords_norm)
            cursor.execute(f"""
                SELECT m.id, m.created_at, m.priority, COUNT(mt.tag) as match_count
                FROM memories m
                JOIN memory_tags mt ON m.id = mt.memory_id
                WHERE lower(mt.tag) IN ({q_marks})
                GROUP BY m.id
                ORDER BY match_count DESC, m.priority DESC, m.created_at DESC
            """, keywords_norm)
            rows = cursor.fetchall()
            memory_ids = [row[0] for row in rows]
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
    except Exception as e:
        return {"status": "error", "error": str(e)}
