"""
This module provides an API endpoint for creating sticky notes.

It defines a FastAPI router with a POST endpoint `/create` that allows users to create new sticky notes.
The endpoint validates the input, particularly the ISO 8601 repeating interval format for periodic notes,
and stores the note in the database. Logging is used for debugging and error tracking.

Dependencies:
    - FastAPI
    - SQLAlchemy ORM
    - isodate for ISO 8601 duration parsing
    - Shared logging configuration

Endpoints:
    - POST /create: Create a new sticky note with optional periodicity.

Raises:
    - HTTPException 422: If the periodicity format is invalid.
    - HTTPException 500: For general errors during note creation.
"""


from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from shared.models.stickynotes import StickyNoteORM, StatusEnum
from app.schemas import StickyNoteCreate, StickyNoteResponse
from app.util import get_db
from isodate import parse_duration

from shared.log_config import get_logger
logger = get_logger(f"stickynotes.{__name__}")

router = APIRouter()


@router.post("/create", response_model=StickyNoteResponse)
async def create_sticky_note(
    note: StickyNoteCreate, db: Session = Depends(get_db)
) -> StickyNoteResponse:
    """
    Creates a new sticky note in the database.

    This asynchronous function handles the creation of a sticky note, including validation of the periodicity field if provided.
    If the periodicity is set, it validates that the value conforms to the ISO 8601 repeating interval format (e.g., 'R/P1D').
    On successful creation, it returns a response containing the status and the ID of the new sticky note.

    Args:
        note (StickyNoteCreate): The data required to create a new sticky note.
        db (Session, optional): The database session dependency.

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