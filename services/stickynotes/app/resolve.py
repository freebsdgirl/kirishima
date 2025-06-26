"""
This module provides an API endpoint for resolving sticky notes.

It defines a FastAPI router with a single GET endpoint `/resolve/{note_id}` that allows users to resolve a sticky note by its ID. The endpoint supports both one-time and recurring sticky notes:

- For recurring notes (with a periodicity), it advances the due date to the next occurrence and keeps the note active.
- For one-time notes, it marks the note as resolved and clears the due date.

The endpoint updates the `updated_at` timestamp on each resolve action and returns the updated sticky note as a response.

Dependencies:
- FastAPI for API routing and dependency injection.
- SQLAlchemy for database operations.
- Utilities for date parsing and logging.
"""

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session
from app.util import get_db
from shared.models.stickynotes import StickyNoteORM, StickyNote, StatusEnum
from fastapi import Depends
from datetime import datetime
from isodate import parse_duration

from shared.log_config import get_logger
logger = get_logger(f"stickynotes.{__name__}")

router = APIRouter()


@router.get("/resolve/{note_id}", response_model=StickyNote)
async def resolve_sticky_note(note_id: str, db: Session = Depends(get_db)) -> StickyNote:
    """
    Resolve a sticky note by its ID, handling both recurring and one-time notes.
    
    Resolves a sticky note by updating its status, due date, and timestamp:
    - For recurring notes, advances the due date to the next occurrence and keeps the note active
    - For one-time notes, marks the note as resolved and clears the due date
    
    Args:
        note_id (str): The unique identifier of the sticky note to resolve
        db (Session, optional): Database session for querying and updating the note
    
    Returns:
        StickyNote: The updated sticky note after resolution
    
    Raises:
        HTTPException: 404 if note not found, 422 for invalid periodicity, 500 for date update failures
    """
    note = db.query(StickyNoteORM).filter(StickyNoteORM.id == note_id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Sticky note not found.")

    now = datetime.now()
    note.updated_at = now  # Always update updated_at on resolve
    if note.periodicity:
        # Recurring note: update due date to next occurrence, keep status active
        try:
            # Extract duration part from ISO 8601 repeating interval (e.g., 'R/P1D' -> 'P1D')
            duration = note.periodicity.split("/")[1]
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Invalid ISO 8601 repeating interval: {e}")
        if not note.due:
            note.due = now
        # Advance due date by the parsed duration
        try:
            delta = parse_duration(duration)
            note.due = (note.due if note.due > now else now) + delta
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to update due date: {e}")
        note.status = StatusEnum.active
    else:
        # One-time note: mark as resolved and clear due date
        note.status = StatusEnum.resolved
        note.due = None
    db.commit()
    db.refresh(note)
    return StickyNote(
        id=note.id,
        text=note.text,
        status=note.status,
        created_at=note.created_at.isoformat() if note.created_at else None,
        updated_at=note.updated_at.isoformat() if note.updated_at else None,
        user_id=note.user_id,
        due=note.due.isoformat() if note.due else "",
        periodicity=note.periodicity
    )