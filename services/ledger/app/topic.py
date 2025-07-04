from shared.models.ledger import CanonicalUserMessage

from fastapi import APIRouter, HTTPException, Query, Path, status
from typing import List, Optional
from datetime import datetime

import sqlite3
import uuid
import json

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

router = APIRouter()


def get_db():
    """
    Retrieves the path to the ledger database from the configuration file and checks its accessibility.

    Opens the '/app/config/config.json' file, loads the database path from the configuration, and attempts to establish a connection to the SQLite database to ensure it is accessible. Raises an HTTPException with status code 500 if there are issues with the configuration file, database access, or any unexpected errors.

    Returns:
        str: The path to the ledger database file.

    Raises:
        HTTPException: If the configuration file is missing, malformed, the database path is not found, the database is inaccessible, or any other unexpected error occurs.
    """
    try:
        with open('/app/config/config.json') as f:
            _config = json.load(f)
        db = _config["db"]["ledger"]
        # Try to open a connection to check if DB is accessible
        with sqlite3.connect(db, timeout=1.0) as conn:
            pass
        return db
    except (FileNotFoundError, KeyError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Configuration error: {e}")
    except sqlite3.OperationalError as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {e}")


def validate_timestamp(ts: str) -> str:
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


def topic_exists(topic_id: str) -> bool:
    """
    Check if a topic with the given ID exists in the database.

    Args:
        topic_id (str): The unique identifier of the topic to check.

    Returns:
        bool: True if the topic exists, False otherwise.
    """
    db = get_db()
    with sqlite3.connect(db, timeout=5.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM topics WHERE id = ?", (topic_id,))
        return cur.fetchone() is not None


@router.post("/topics", response_model=str)
def create_topic(name: str):
    """
    Create a new topic in the database with the given name and return its UUID.

    Args:
        name (str): The name of the topic to create.

    Returns:
        str: The UUID of the newly created topic.

    Raises:
        HTTPException: If a database error occurs during topic creation.
    """
    topic_id = str(uuid.uuid4())
    db = get_db()
    try:
        with sqlite3.connect(db, timeout=5.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                "INSERT INTO topics (id, name) VALUES (?, ?)",
                (topic_id, name)
            )
            conn.commit()
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Database error: {e}")
    return topic_id


@router.get("/topics/{topic_id}/messages", response_model=List[CanonicalUserMessage])
def get_messages_by_topic(topic_id: str) -> List[CanonicalUserMessage]:
    """
    Retrieve all user messages associated with a given topic ID.

    This function checks if the specified topic exists, then queries the database for all messages
    related to the topic, ordered by their ID. It parses the 'tool_calls' field from JSON if necessary,
    constructs CanonicalUserMessage objects, and filters out messages with the role 'tool' as well as
    assistant messages with empty content.

    Args:
        topic_id (str): The unique identifier of the topic.

    Returns:
        List[CanonicalUserMessage]: A list of user messages for the topic, excluding tool messages and
        assistant messages with empty content.

    Raises:
        HTTPException: If the topic does not exist (404 Not Found).
    """
    if not topic_exists(topic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")
    db = get_db()
    with sqlite3.connect(db, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_messages WHERE topic_id = ? ORDER BY id", (topic_id,))
        columns = [col[0] for col in cur.description]
        raw_messages = [dict(zip(columns, row)) for row in cur.fetchall()]
        # Parse tool_calls if it's a string
        for msg in raw_messages:
            if 'tool_calls' in msg and isinstance(msg['tool_calls'], str):
                try:
                    msg['tool_calls'] = json.loads(msg['tool_calls'])
                except Exception:
                    msg['tool_calls'] = None
        messages = [CanonicalUserMessage(**msg) for msg in raw_messages]
        # Filter out tool messages and assistant messages with empty content
        messages = [
            msg for msg in messages
            if not (
                getattr(msg, 'role', None) == 'tool' or
                (getattr(msg, 'role', None) == 'assistant' and not getattr(msg, 'content', None))
            )
        ]
        return messages


@router.get("/topics/ids")
def get_topic_ids_in_timeframe(
    start: str = Query(..., description="Start timestamp (YYYY-MM-DD HH:MM:SS)"),
    end: str = Query(..., description="End timestamp (YYYY-MM-DD HH:MM:SS)")
) -> List[str]:
    """
    Retrieve a list of unique topic IDs from user messages within a specified time frame.

    Args:
        start (str): Start timestamp in the format "YYYY-MM-DD HH:MM:SS".
        end (str): End timestamp in the format "YYYY-MM-DD HH:MM:SS".

    Returns:
        List[str]: A list of distinct topic IDs found in user messages between the start and end timestamps.

    Raises:
        ValueError: If the provided timestamps are invalid or not in the expected format.
    """
    start = validate_timestamp(start)
    end = validate_timestamp(end)
    db = get_db()
    with sqlite3.connect(db, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute(
            "SELECT DISTINCT topic_id FROM user_messages WHERE created_at >= ? AND created_at <= ? AND topic_id IS NOT NULL",
            (start, end)
        )
        topic_ids = [row[0] for row in cur.fetchall()]
    return topic_ids


@router.patch("/topics/{topic_id}/assign")
def assign_topic_to_messages(
    topic_id: str = Path(...),
    start: str = Query(..., description="Start timestamp (YYYY-MM-DD HH:MM:SS[.sss])"),
    end: str = Query(..., description="End timestamp (YYYY-MM-DD HH:MM:SS[.sss])")
):
    """
    Assigns a topic to all user messages within a specified time range.

    Args:
        topic_id (str): The ID of the topic to assign.
        start (str): The start timestamp in the format 'YYYY-MM-DD HH:MM:SS[.sss]'.
        end (str): The end timestamp in the format 'YYYY-MM-DD HH:MM:SS[.sss]'.

    Raises:
        HTTPException: If the topic does not exist.
        HTTPException: If no messages are found in the given timeframe.

    Returns:
        dict: A dictionary containing the number of updated messages, e.g., {"updated": <rowcount>}.
    """
    logger.debug(f"Assigning topic {topic_id} to messages from {start} to {end}")
    start = validate_timestamp(start)
    end = validate_timestamp(end)
    if not topic_exists(topic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")
    db = get_db()
    with sqlite3.connect(db, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        # check to see if there are any messages in the given timeframe
        cur.execute(
            "SELECT COUNT(*) FROM user_messages WHERE created_at >= ? AND created_at <= ?",
            (start, end)
        )
        count = cur.fetchone()[0]
        if count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No messages found in the given timeframe.")
        cur.execute(
            "UPDATE user_messages SET topic_id = ? WHERE created_at >= ? AND created_at <= ?",
            (topic_id, start, end)
        )
        conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No messages found in the given timeframe.")
    return {"updated": cur.rowcount}

@router.delete("/topics/{topic_id}")
def delete_topic(topic_id: str):
    """
    Deletes a topic from the database by its ID.

    Args:
        topic_id (str): The unique identifier of the topic to delete.

    Raises:
        HTTPException: If the topic does not exist (404 Not Found).
        HTTPException: If the topic was not found or already deleted after attempting deletion (404 Not Found).

    Returns:
        dict: A dictionary containing the number of deleted topics, e.g., {"deleted": 1}.
    """
    if not topic_exists(topic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")
    db = get_db()
    with sqlite3.connect(db, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute("DELETE FROM topics WHERE id = ?", (topic_id,))
        conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Topic not found or already deleted.")
    return {"deleted": cur.rowcount}


@router.get("/topics/recent", response_model=List[dict])
def get_recent_topics(
    n: int = Query(5, description="Number of recent topics to return"),
    user_id: Optional[str] = Query(None, description="User ID to filter topics by")
):
    """
    Retrieve a list of recent topics, optionally filtered by user ID.

    Args:
        n (int, optional): Number of recent topics to return. Defaults to 5.
        user_id (Optional[str], optional): User ID to filter topics by. If None, topics are not filtered by user.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries, each containing the 'id' and 'name' of a recent topic.

    Notes:
        - Topics are determined from the 'user_messages' table, ordered by 'created_at' in descending order.
        - Only distinct, non-null topic IDs are considered.
        - If a user_id is provided, only topics associated with that user are returned.
    """
    db = get_db()
    with sqlite3.connect(db, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        if user_id:
            cur.execute(
                "SELECT DISTINCT topic_id FROM user_messages WHERE topic_id IS NOT NULL AND user_id = ? ORDER BY created_at DESC",
                (user_id,)
            )
        else:
            cur.execute(
                "SELECT DISTINCT topic_id FROM user_messages WHERE topic_id IS NOT NULL ORDER BY created_at DESC"
            )
        topic_ids = []
        seen = set()
        for row in cur.fetchall():
            tid = row[0]
            if tid and tid not in seen:
                topic_ids.append(tid)
                seen.add(tid)
            if len(topic_ids) >= n:
                break
        topics = []
        for tid in topic_ids:
            cur.execute("SELECT name FROM topics WHERE id = ?", (tid,))
            result = cur.fetchone()
            if result:
                topics.append({"id": tid, "name": result[0]})
        return topics


@router.get("/topics/id/{topic_id}", response_model=dict)
def get_topic_by_id(topic_id: str):
    """
    Retrieve a topic by its unique identifier.

    Args:
        topic_id (str): The unique identifier of the topic to retrieve.

    Returns:
        dict: A dictionary containing the topic's 'id' and 'name'.

    Raises:
        HTTPException: If the topic does not exist, raises a 404 Not Found error.
    """
    if not topic_exists(topic_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")
    db = get_db()
    with sqlite3.connect(db, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM topics WHERE id = ?", (topic_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found.")
        return {"id": row[0], "name": row[1]}


@router.get("/topics", response_model=List[dict])
def get_all_topics():
    """
    Retrieve all topics from the database.

    Returns:
        list of dict: A list of dictionaries, each containing the 'id' and 'name' of a topic,
        ordered alphabetically by name.
    """
    db = get_db()
    with sqlite3.connect(db, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM topics ORDER BY name")
        rows = cur.fetchall()
        return [{"id": row[0], "name": row[1]} for row in rows]