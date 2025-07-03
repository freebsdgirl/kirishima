from fastapi import APIRouter, HTTPException, Query, Path
from typing import List, Optional
from datetime import datetime
import sqlite3
import uuid
import json
from shared.models.ledger import CanonicalUserMessage
from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")
router = APIRouter()

def get_db():
    try:
        with open('/app/config/config.json') as f:
            _config = json.load(f)
        db = _config["db"]["ledger"]
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

def validate_timestamp(ts: str) -> str:
    # Accepts 'YYYY-MM-DD HH:MM:SS' or 'YYYY-MM-DD HH:MM:SS.sss'
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            dt = datetime.strptime(ts, fmt)
            # Always return with millisecond precision
            return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        except ValueError:
            continue
    raise HTTPException(status_code=400, detail=f"Invalid timestamp format: {ts}. Use 'YYYY-MM-DD HH:MM:SS[.sss]'.")

def topic_exists(topic_id: str) -> bool:
    db = get_db()
    with sqlite3.connect(db, timeout=5.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM topics WHERE id = ?", (topic_id,))
        return cur.fetchone() is not None

@router.post("/topics", response_model=str)
def create_topic(name: str):
    """Create a new topic and return its UUID."""
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
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    return topic_id

@router.get("/topics/{topic_id}/messages", response_model=List[CanonicalUserMessage])
def get_messages_by_topic(topic_id: str) -> List[CanonicalUserMessage]:
    """List all user_messages assigned to a specific topic id."""
    if not topic_exists(topic_id):
        raise HTTPException(status_code=404, detail="Topic not found.")
    db = get_db()
    with sqlite3.connect(db, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_messages WHERE topic_id = ? ORDER BY id", (topic_id,))
        columns = [col[0] for col in cur.description]
        raw_messages = [dict(zip(columns, row)) for row in cur.fetchall()]
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
    """List all topic_ids in user_messages in a given timeframe (to the second)."""
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
    logger.debug(f"Assigning topic {topic_id} to messages from {start} to {end}")
    """Assign all user_messages in a given timeframe (to the millisecond) to a topic id."""
    start = validate_timestamp(start)
    end = validate_timestamp(end)
    if not topic_exists(topic_id):
        raise HTTPException(status_code=404, detail="Topic not found.")
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
            raise HTTPException(status_code=404, detail="No messages found in the given timeframe.")
        cur.execute(
            "UPDATE user_messages SET topic_id = ? WHERE created_at >= ? AND created_at <= ?",
            (topic_id, start, end)
        )
        conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="No messages found in the given timeframe.")
    return {"updated": cur.rowcount}

@router.delete("/topics/{topic_id}")
def delete_topic(topic_id: str):
    """Delete a topic by id."""
    if not topic_exists(topic_id):
        raise HTTPException(status_code=404, detail="Topic not found.")
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
    """Return the most recent N topics (id and name), based on most recent user_messages for a user, ordered by created_at descending."""
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


# resolve a topic id to a name
@router.get("/topics/id/{topic_id}", response_model=dict)
def get_topic_by_id(topic_id: str):
    """Get topic details by id."""
    if not topic_exists(topic_id):
        raise HTTPException(status_code=404, detail="Topic not found.")
    db = get_db()
    with sqlite3.connect(db, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM topics WHERE id = ?", (topic_id,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Topic not found.")
        return {"id": row[0], "name": row[1]}

# return a list of all topics and their ids
@router.get("/topics", response_model=List[dict])
def get_all_topics():
    """Get a list of all topics with their ids."""
    db = get_db()
    with sqlite3.connect(db, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute("SELECT id, name FROM topics ORDER BY name")
        rows = cur.fetchall()
        return [{"id": row[0], "name": row[1]} for row in rows]