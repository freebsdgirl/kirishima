import sqlite3
import json
import uuid
from datetime import datetime

# Load config to get the memories DB path
with open('/app/config/config.json') as f:
    _config = json.load(f)
MEMORIES_DB = _config['db']['memories']

def memory_add(memory: str, keywords: list, topic: str, priority: float):
    """
    Add a new memory and its tags to the memories database.
    Args:
        memory (str): The memory text to save.
        tags (list): List of tags/keywords associated with the memory.
        topic (str): The topic associated with the memory
        priority (float): Priority level (0.0 to 1.0).
    Returns:
        str: The ID of the new memory, or an error dict on failure.
    """
    memory_id = str(uuid.uuid4())
    user_id = 'c63989a3-756c-4bdf-b0c2-13d01e129e02'  # Stub: replace with actual user_id logic
    # Use local time instead of UTC
    created_at = datetime.now().isoformat()
    try:
        with sqlite3.connect(MEMORIES_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.execute(
                """
                INSERT INTO memories (id, user_id, memory, created_at, priority)
                VALUES (?, ?, ?, ?, ?)
                """,
                (memory_id, user_id, memory, created_at, priority)
            )
            for tag in keywords:
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO memory_tags (memory_id, tag)
                    VALUES (?, ?)
                    """,
                    (memory_id, tag)
                )
            conn.commit()
     
            if topic:
                # verify topic matches one of the allowed topics
                allowed_topics = [
                    "Health", "Career", "Family", "Personal", "Technical Projects",
                    "Social", "Finance", "Self-care", "Environment", "Hobbies",
                    "Admin", "Philosophy"
                ]
                if topic not in allowed_topics:
                    return {"status": "error", "error": f"Invalid topic: {topic}. Allowed topics are: {', '.join(allowed_topics)}"}
                    
                cursor.execute(
                        """
                        INSERT INTO memory_topic (memory_id, topic)
                        VALUES (?, ?)
                        """,
                        (memory_id, topic)  # Stub: replace with actual topic logic
                    )
                conn.commit()
        return {"status": "memory created", "id": memory_id}
    except Exception as e:
        return {"status": "error", "error": str(e)}
