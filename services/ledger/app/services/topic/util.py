from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from app.util import _open_conn

import uuid
from datetime import datetime

from fastapi import HTTPException, status

def _find_or_create_topic(name: str) -> str:
    """
    Find an existing topic by name or create a new one if it doesn't exist.
    
    This function prevents duplicate topics with the same name by first checking
    if a topic with the given name already exists. If found, returns the existing
    topic's ID. If not found, creates a new topic and returns its ID.
    
    Args:
        name (str): The name of the topic to find or create.
    
    Returns:
        str: The UUID of the existing or newly created topic.
    """
    logger.debug(f"Finding or creating topic with name: {name}")
    if not name:
        raise ValueError("Topic name cannot be empty")
    with _open_conn() as conn:
        # First, try to find existing topic with this name
        cursor = conn.execute(
            "SELECT id FROM topics WHERE name = ? LIMIT 1",
            (name,)
        )
        result = cursor.fetchone()
        
        if result:
            logger.debug(f"Topic '{name}' already exists with ID: {result[0]}")
            # Topic already exists, return its ID
            return result[0]
        
        # Topic doesn't exist, create a new one
        topic_id = str(uuid.uuid4())
        
        # Check if created_at column exists in topics table
        cursor = conn.execute("PRAGMA table_info(topics)")
        columns = [row[1] for row in cursor.fetchall()]
        
        logger.debug(f"Creating new topic '{name}' with ID: {topic_id}")
        if 'created_at' in columns:
            # Insert with created_at if column exists
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT INTO topics (id, name, created_at) VALUES (?, ?, ?)",
                (topic_id, name, now)
            )
        else:
            # Insert without created_at if column doesn't exist
            conn.execute(
                "INSERT INTO topics (id, name) VALUES (?, ?)",
                (topic_id, name)
            )
        
        conn.commit()
        logger.debug(f"New topic '{name}' created with ID: {topic_id}")
        return topic_id


def _topic_exists(topic_id: str) -> bool:
    """
    Check if a topic with the given ID exists in the database.

    Args:
        topic_id (str): The unique identifier of the topic to check.

    Returns:
        bool: True if the topic exists, False otherwise.
    """
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM topics WHERE id = ?", (topic_id,))
        return cur.fetchone() is not None


def _validate_timestamp(ts: str) -> str:
    """
    Validates and normalizes a timestamp string.

    Accepts timestamp strings in the formats 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DD HH:MM:SS.sss'.
    Returns the timestamp as a string with millisecond precision ('YYYY-MM-DD HH:MM:SS.sss').
    Raises an HTTPException with status 400 if the input does not match the expected formats.

    Args:
        ts (str): The timestamp string to validate.

    Returns:
        str: The normalized timestamp string with millisecond precision.

    Raises:
        HTTPException: If the input timestamp format is invalid.
    """
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(ts, fmt)
            # Always return with millisecond precision
            return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        except ValueError:
            continue
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid timestamp format: {ts}. Use 'YYYY-MM-DD HH:MM:SS[.sss]'.")

