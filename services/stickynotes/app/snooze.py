"""
This module provides an API endpoint to snooze sticky notes for a specified duration.
Endpoints:
    - POST /snooze/{note_id}: Snoozes a sticky note by its ID for a given ISO 8601 duration, updating its status and due date.
Dependencies:
    - FastAPI for API routing and HTTP exception handling.
    - SQLAlchemy for database session management.
    - isodate for parsing ISO 8601 durations.
    - shared.models.stickynotes for ORM models and enums.
    - app.util for database session dependency.
    - shared.log_config for logging.
Logging:
    - Logs snooze actions with note ID and new due date.
"""


from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from fastapi import Depends
from isodate import parse_duration
from datetime import datetime

from shared.models.stickynotes import StickyNoteORM, StickyNote, StatusEnum
from app.util import get_db
from shared.log_config import get_logger
logger = get_logger(f"stickynotes.{__name__}")

router = APIRouter()


@router.post("/snooze/{note_id}", response_model=StickyNote)
async def snooze_sticky_note(note_id: str, snooze_time: str, db: Session = Depends(get_db)) -> StickyNote:
    """
    Snooze a sticky note by its ID for a specified ISO 8601 duration.

    This updates the sticky note's status to snoozed and sets the due date to now + snooze_time.
    
    Args:
        note_id (str): The ID of the sticky note to snooze.
        snooze_time (str): An ISO 8601 duration.

    Returns:
        StickyNote: The updated sticky note with snooze status.
    """
    note = db.query(StickyNoteORM).filter(StickyNoteORM.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Sticky note not found.")
    try:
        delta = parse_duration(snooze_time)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Invalid ISO 8601 duration: {e}")
    now = datetime.now()
    note.due = now + delta
    note.status = StatusEnum.snoozed
    note.updated_at = now
    db.commit()
    db.refresh(note)
    logger.info(f"Snoozed sticky note {note_id} until {note.due}.")
    return StickyNote(
        id=note.id,
        text=note.text,
        status=note.status,
        created_at=note.created_at.isoformat() if note.created_at else None,
        updated_at=note.updated_at.isoformat() if note.updated_at else None,
        user_id=note.user_id,
        due=note.due.isoformat() if note.due else None,
        periodicity=note.periodicity
    )