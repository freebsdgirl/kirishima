"""
Business logic for sticky note operations.

This module contains the core business logic for sticky note operations,
separated from the FastAPI route handlers.
"""

from sqlalchemy.orm import Session
from shared.models.stickynotes import StickyNoteORM, StatusEnum, StickyNote
from app.schemas import StickyNoteCreate, StickyNoteResponse
from isodate import parse_duration
from fastapi import HTTPException
from datetime import datetime

from shared.log_config import get_logger
logger = get_logger(f"stickynotes.{__name__}")


async def _create_sticky_note(
    note: StickyNoteCreate, 
    db: Session
) -> StickyNoteResponse:
    """
    Creates a new sticky note in the database.

    This asynchronous function handles the creation of a sticky note, including 
    validation of the periodicity field if provided.

    Args:
        note (StickyNoteCreate): The data required to create a new sticky note.
        db (Session): The database session.

    Returns:
        StickyNoteResponse: The response containing the status and ID of the created sticky note.

    Raises:
        HTTPException: If the periodicity format is invalid (422) or if any other error occurs during creation (500).
    """
    try:
        # If periodicity is set, validate the ISO 8601 repeating interval format (e.g., 'R/P1D')
        if note.periodicity:
            try:
                # Just check that the string splits and the duration parses
                duration = note.periodicity.split("/")[1]
                _ = parse_duration(duration)
            except Exception as e:
                raise HTTPException(status_code=422, detail=f"Invalid ISO 8601 repeating interval: {e}")
        
        new_note = StickyNoteORM(
            text=note.text,
            due=note.due,
            periodicity=note.periodicity,
            user_id=note.user_id,
            status=StatusEnum.active,
        )

        logger.debug(f"Creating sticky note: {new_note.text} for user {new_note.user_id}")
        db.add(new_note)
        db.commit()
        db.refresh(new_note)
        logger.info(f"Created sticky note: {new_note.id}")
        return StickyNoteResponse(status="success", id=new_note.id)
    except Exception as e:
        logger.error(f"Failed to create sticky note: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create sticky note: {e}")


async def _list_sticky_notes(
    user_id: str,
    db: Session
) -> list[StickyNote]:
    """
    List all non-resolved sticky notes for a specific user.
    
    Args:
        user_id (str): The unique identifier of the user whose sticky notes are to be retrieved.
        db (Session): Database session for querying sticky notes.
    
    Returns:
        list[StickyNote]: A list of active sticky notes for the specified user, excluding resolved notes.
    """
    logger.info(f"Listing sticky notes for user_id={user_id}.")
    notes = db.query(StickyNoteORM).filter(
        StickyNoteORM.user_id == user_id,
        StickyNoteORM.status != "resolved"
    ).all()
    return [StickyNote(
        id=n.id,
        text=n.text,
        status=n.status,
        created_at=n.created_at.isoformat() if n.created_at else None,
        updated_at=n.updated_at.isoformat() if n.updated_at else None,
        user_id=n.user_id,
        due=n.due.isoformat() if n.due else None,
        periodicity=n.periodicity
    ) for n in notes]


async def _resolve_sticky_note(note_id: str, db: Session) -> StickyNote:
    """
    Resolve a sticky note by its ID, handling both recurring and one-time notes.
    
    Resolves a sticky note by updating its status, due date, and timestamp:
    - For recurring notes, advances the due date to the next occurrence and keeps the note active
    - For one-time notes, marks the note as resolved and clears the due date
    
    Args:
        note_id (str): The unique identifier of the sticky note to resolve
        db (Session): Database session for querying and updating the note
    
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


async def _snooze_sticky_note(note_id: str, snooze_time: str, db: Session) -> StickyNote:
    """
    Snooze a sticky note by its ID for a specified ISO 8601 duration.

    This updates the sticky note's status to snoozed and sets the due date to now + snooze_time.
    
    Args:
        note_id (str): The ID of the sticky note to snooze.
        snooze_time (str): An ISO 8601 duration.
        db (Session): Database session for querying and updating the note.

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


async def _check_due_stickynotes(user_id: str, db: Session) -> list[StickyNote]:
    """
    Check and retrieve due or overdue sticky notes for a specific user.
    
    Retrieves all sticky notes for the given user that are currently due or overdue,
    excluding resolved notes. Logs the number of notes found.
    
    Args:
        user_id (str): The unique identifier of the user whose sticky notes are to be checked.
        db (Session): Database session for querying sticky notes.
    
    Returns:
        list[StickyNote]: A list of due or overdue sticky notes, converted to StickyNote objects.
    """
    now = datetime.now()
    notes = db.query(StickyNoteORM).filter(
        StickyNoteORM.user_id == user_id,
        StickyNoteORM.status != "resolved",
        StickyNoteORM.due != None,
        StickyNoteORM.due <= now
    ).all()
    logger.info(f"Found {len(notes)} due/overdue sticky notes for user_id={user_id}.")
    return [StickyNote(
        id=n.id,
        text=n.text,
        status="active",
        created_at=n.created_at.isoformat() if n.created_at else None,
        updated_at=n.updated_at.isoformat() if n.updated_at else None,
        user_id=n.user_id,
        due=n.due.isoformat() if n.due else None,
        periodicity=n.periodicity
    ) for n in notes]
