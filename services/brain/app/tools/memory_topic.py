import sqlite3
import json
import uuid
from datetime import datetime
from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

# Load config to get the memories DB path
with open('/app/config/config.json') as f:
    _config = json.load(f)
MEMORIES_DB = _config['db']['memories']

def memory_topic(memory_id: str, topic_id: str):
    """
    Assign a topic to a memory.
    Args:
        memory_id (str): The ID of the memory to assign the topic to.
        topic_id (str): The ID of the topic to assign.
    Returns:
        dict: Status message indicating success or failure.
    """
    logger.info(f"Assigning topic {topic_id} to memory {memory_id}")
    try:
        with sqlite3.connect(MEMORIES_DB) as conn:
            cursor = conn.cursor()
            
            # Assign topic to memory
            cursor.execute(
                "INSERT OR IGNORE INTO memory_topics (memory_id, topic_id) VALUES (?, ?)",
                (memory_id, topic_id)
            )
            conn.commit()
        
        return {"status": "ok", "message": f"Topic {topic_id} assigned to memory {memory_id}."}
    
    except sqlite3.Error as e:
        return {"status": "error", "error": str(e)}