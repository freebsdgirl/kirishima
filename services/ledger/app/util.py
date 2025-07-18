import sqlite3
import json
import uuid
from datetime import datetime, time, timedelta
from typing import Optional

def _open_conn() -> sqlite3.Connection:
    """
    Opens a SQLite database connection using the path specified in the configuration file.
    Reads the database path from '/app/config/config.json' under the key ["db"]["ledger"],
    establishes a connection with a 5-second timeout, sets the journal mode to WAL,
    and enables foreign key constraints.
    Returns:
        sqlite3.Connection: An open connection to the specified SQLite database.
    """
    with open('/app/config/config.json') as f:
        _config = json.load(f)
    db = _config["db"]["ledger"]
    conn = sqlite3.connect(db, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def get_period_range(period: str, date_str: Optional[str] = None):
    """
    Returns the start and end datetime objects for a given period of the day.
    Args:
        period (str): The period of the day. Must be one of "night", "morning", "afternoon", "evening", or "day".
        date_str (Optional[str], optional): The date in "YYYY-MM-DD" format. If not provided, uses the current date,
            or for "evening" and "day" periods, defaults to the previous day.
    Returns:
        Tuple[datetime, datetime]: A tuple containing the start and end datetime objects for the specified period.
    Raises:
        ValueError: If the provided period is not one of the accepted values.
    """
    if date_str is None:
        now = datetime.now()
        if period in ("evening", "day"):
            date = (now - timedelta(days=1)).date()
        else:
            date = now.date()
    else:
        date = datetime.strptime(date_str, "%Y-%m-%d").date()
    if period == "night":
        start = datetime.combine(date, time(0, 0))
        end = datetime.combine(date, time(5, 59, 59, 999999))
    elif period == "morning":
        start = datetime.combine(date, time(6, 0))
        end = datetime.combine(date, time(11, 59, 59, 999999))
    elif period == "afternoon":
        start = datetime.combine(date, time(12, 0))
        end = datetime.combine(date, time(17, 59, 59, 999999))
    elif period == "evening":
        start = datetime.combine(date, time(18, 0))
        end = datetime.combine(date, time(23, 59, 59, 999999))
    elif period == "day":
        start = datetime.combine(date, time(0, 0))
        end = datetime.combine(date, time(23, 59, 59, 999999))
    else:
        raise ValueError("Invalid period")
    return start, end

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
    with _open_conn() as conn:
        # First, try to find existing topic with this name
        cursor = conn.execute(
            "SELECT id FROM topics WHERE name = ? LIMIT 1",
            (name,)
        )
        result = cursor.fetchone()
        
        if result:
            # Topic already exists, return its ID
            return result[0]
        
        # Topic doesn't exist, create a new one
        topic_id = str(uuid.uuid4())
        
        # Check if created_at column exists in topics table
        cursor = conn.execute("PRAGMA table_info(topics)")
        columns = [row[1] for row in cursor.fetchall()]
        
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
        return topic_id
