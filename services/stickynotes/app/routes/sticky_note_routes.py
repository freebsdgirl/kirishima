"""
FastAPI routes for sticky note operations.

This module defines the HTTP endpoints for the sticky notes service,
delegating business logic to the service layer.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.schemas import StickyNoteCreate, StickyNoteResponse
from app.services.util import get_db
from shared.models.stickynotes import StickyNote
from app.services.sticky_note_service import (
    _create_sticky_note,
    _list_sticky_notes, 
    _resolve_sticky_note,
    _snooze_sticky_note,
    _check_due_stickynotes
)

router = APIRouter()


@router.post("/create", response_model=StickyNoteResponse)
async def create_sticky_note(
    note: StickyNoteCreate, 
    db: Session = Depends(get_db)
) -> StickyNoteResponse:
    """
    Create a new sticky note in the database.

    This endpoint allows users to create a sticky note with optional periodicity.
    It validates the periodicity format if provided and stores the note in the database.

    Args:
        note (StickyNoteCreate): The data required to create a new sticky note.
        db (Session): The database session dependency (injected by FastAPI).

    Returns:
        StickyNoteResponse: The response containing the status and ID of the created sticky note.
    """
    return await _create_sticky_note(note=note, db=db)


@router.get("/list", response_model=list[StickyNote])
async def list_sticky_notes(
    user_id: str = Query(..., description="The ID of the user whose sticky notes to list."),
    db: Session = Depends(get_db)
) -> list[StickyNote]:
    """
    List all non-resolved sticky notes for a specific user.

    This endpoint retrieves all active sticky notes for the given user, excluding any notes that have been resolved.

    Args:
        user_id (str): The unique identifier of the user whose sticky notes are to be retrieved.
        db (Session): The database session dependency.

    Returns:
        list[StickyNote]: A list of active sticky notes for the specified user.
    """
    return await _list_sticky_notes(user_id=user_id, db=db)


@router.get("/resolve/{note_id}", response_model=StickyNote)
async def resolve_sticky_note(
    note_id: str,
    db: Session = Depends(get_db)
) -> StickyNote:
    """
    Resolve a sticky note by its ID.

    This endpoint handles both recurring and one-time sticky notes:
    - For recurring notes, it updates the due date to the next occurrence and keeps the note active.
    - For one-time notes, it marks the note as resolved and clears the due date.

    Args:
        note_id (str): The unique identifier of the sticky note to resolve.
        db (Session): The database session dependency.

    Returns:
        StickyNote: The updated sticky note after resolution.
    """
    return await _resolve_sticky_note(note_id=note_id, db=db)


@router.post("/snooze/{note_id}", response_model=StickyNote)
async def snooze_sticky_note(
    note_id: str,
    snooze_time: str,
    db: Session = Depends(get_db)
) -> StickyNote:
    """
    Snooze a sticky note by its ID for a specified ISO 8601 duration.

    This endpoint updates the sticky note's status to snoozed and sets the due date to now + snooze_time.

    Args:
        note_id (str): The ID of the sticky note to snooze.
        snooze_time (str): An ISO 8601 duration string (e.g., "PT1H" for 1 hour).
        db (Session): The database session dependency.

    Returns:
        StickyNote: The updated sticky note with snooze status.
    """
    return await _snooze_sticky_note(note_id=note_id, snooze_time=snooze_time, db=db)


@router.get("/check", response_model=list[StickyNote])
async def check_due_stickynotes(
    user_id: str = Query(..., description="The ID of the user whose due sticky notes to check."),
    db: Session = Depends(get_db)
) -> list[StickyNote]:
    """
    Check and retrieve due or overdue sticky notes for a specific user.

    Args:
        user_id (str): The unique identifier of the user whose sticky notes are to be checked.
        db (Session): The database session dependency.

    Returns:
        list[StickyNote]: A list of due or overdue sticky notes.
    """
    return await _check_due_stickynotes(user_id=user_id, db=db)
