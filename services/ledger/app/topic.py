from fastapi import APIRouter, HTTPException, Query, Path
from typing import List, Optional
from datetime import datetime
import sqlite3
import uuid
import json

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
    try:
        # Accepts 'YYYY-MM-DD HH:MM:SS'
        datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
        return ts
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid timestamp format: {ts}. Use 'YYYY-MM-DD HH:MM:SS'.")

def topic_exists(topic_id: str) -> bool:
    db = get_db()
    with sqlite3.connect(db, timeout=5.0) as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM topics WHERE id = ?", (topic_id,))
        return cur.fetchone() is not None

@router.post("/topics", response_model=str)
def create_topic(name: Optional[str] = None, description: Optional[str] = None):
    """Create a new topic and return its UUID."""
    topic_id = str(uuid.uuid4())
    db = get_db()
    try:
        with sqlite3.connect(db, timeout=5.0) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute(
                "INSERT INTO topics (id, name, description) VALUES (?, ?, ?)",
                (topic_id, name, description)
            )
            conn.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    return topic_id

@router.get("/topics/{topic_id}/messages")
def get_messages_by_topic(topic_id: str) -> List[dict]:
    """List all user_messages assigned to a specific topic id."""
    if not topic_exists(topic_id):
        raise HTTPException(status_code=404, detail="Topic not found.")
    db = get_db()
    with sqlite3.connect(db, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        cur.execute("SELECT * FROM user_messages WHERE topic_id = ? ORDER BY id", (topic_id,))
        columns = [col[0] for col in cur.description]
        messages = [dict(zip(columns, row)) for row in cur.fetchall()]
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
    start: str = Query(..., description="Start timestamp (YYYY-MM-DD HH:MM:SS)"),
    end: str = Query(..., description="End timestamp (YYYY-MM-DD HH:MM:SS)")
):
    """Assign all user_messages in a given timeframe (to the second) to a topic id."""
    start = validate_timestamp(start)
    end = validate_timestamp(end)
    if not topic_exists(topic_id):
        raise HTTPException(status_code=404, detail="Topic not found.")
    db = get_db()
    with sqlite3.connect(db, timeout=5.0) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
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
