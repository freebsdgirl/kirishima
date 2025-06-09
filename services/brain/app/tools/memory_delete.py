import sqlite3
import json
from pathlib import Path

def memory_delete(memory_id: str):
    """
    Delete a memory and its tags from the memories database by memory ID.
    Args:
        memory_id (str): The ID of the memory to delete.
    Returns:
        dict: Status of the operation.
    """
    # Load config to get the memories DB path
    try:
        with open('/app/shared/config.json') as f:
            _config = json.load(f)
        MEMORIES_DB = _config['db']['memories']
        with sqlite3.connect(MEMORIES_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            conn.commit()
            if cursor.rowcount == 0:
                return {"status": "error", "error": "No memory found with that ID."}
        return {"status": "memory deleted", "id": memory_id}
    except Exception as e:
        return {"status": "error", "error": str(e)}
