import sqlite3
import json
from pathlib import Path
from typing import List

def memory_search(keywords: List[str] = None, topic: str = None, memory_id: str = None):
    """
    Search for memories by keywords (tags), by topic, or by memory_id. Only one of keywords, topic, or memory_id may be provided.
    Args:
        keywords (List[str], optional): List of keywords to search for.
        topic (str, optional): Topic to search for.
        memory_id (str, optional): Memory ID to search for.
    Returns:
        dict: Status and list of matching memory records.
    """
    # Only one of keywords, topic, or memory_id may be provided
    provided = [x is not None and x != [] for x in [keywords, topic, memory_id]]
    if sum(provided) != 1:
        return {"status": "error", "error": "Provide exactly one of keywords, topic, or memory_id."}
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
            elif topic:
                cursor.execute("""
                    SELECT m.id, m.created_at, m.priority
                    FROM memories m
                    JOIN memory_topic mt ON m.id = mt.memory_id
                    WHERE mt.topic = ?
                    ORDER BY m.created_at DESC
                """, (topic,))
                rows = cursor.fetchall()
                memory_ids = [row[0] for row in rows]
            else:  # memory_id
                cursor.execute("SELECT id, user_id, memory, created_at, access_count, last_accessed, priority FROM memories WHERE id = ?", (memory_id,))
                row = cursor.fetchone()
                if not row:
                    return {"status": "ok", "memories": []}
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
    except Exception as e:
        return {"status": "error", "error": str(e)}
