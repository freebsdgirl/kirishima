"""
This module defines an API endpoint for checking due or overdue sticky notes for a specific user.

Routes:
    GET /check:
        Returns a list of sticky notes for the specified user that are due now or overdue.
        - Query Parameters:
            - user_id (str): The ID of the user whose due sticky notes are to be checked.
        - Response:
            - List of StickyNote objects representing the due or overdue sticky notes.

Dependencies:
    - FastAPI for API routing and dependency injection.
    - SQLAlchemy for database session management.
    - Shared logging and models for consistent logging and data representation.

Logging:
    Logs the number of due/overdue sticky notes found for the given user.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from datetime import datetime
from app.util import get_db
from shared.log_config import get_logger
from shared.models.stickynotes import StickyNoteORM, StickyNote

logger = get_logger(f"stickynotes.{__name__}")

router = APIRouter()

@router.get("/check", response_model=list[StickyNote])
async def check_due_stickynotes(
    user_id: str = Query(..., description="The ID of the user whose due sticky notes to check."),
    db: Session = Depends(get_db)
) -> list[StickyNote]:
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