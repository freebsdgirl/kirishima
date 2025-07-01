import sqlite3
import json
from pathlib import Path

def memory_list():
    """
    List all memories along with their keywords.
    Returns:
        dict: Status and list of memories, each with a list of keywords.
    """
    try:
        with open('/app/config/config.json') as f:
            _config = json.load(f)
        MEMORIES_DB = _config['db']['memories']
        with sqlite3.connect(MEMORIES_DB) as conn:
            cursor = conn.cursor()
            # Fetch all memories
            cursor.execute("SELECT id, user_id, memory, created_at, access_count, last_accessed, priority FROM memories")
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
        return {"status": "ok", "memories": result}
    except Exception as e:
        return {"status": "error", "error": str(e)}
