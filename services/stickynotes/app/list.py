"""
This module defines the API endpoint for listing sticky notes associated with a specific user.
Routes:
    GET /list:
        - Lists all non-resolved sticky notes for a given user.
        - Query Parameters:
            - user_id (str): The ID of the user whose sticky notes are to be listed.
        - Returns:
            - List of StickyNote objects representing the user's active sticky notes.
Dependencies:
    - FastAPI APIRouter for route definition.
    - SQLAlchemy Session for database access.
    - Utility functions for database session management and logging.
    - Shared models for sticky note ORM and schema definitions.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.util import get_db
from shared.log_config import get_logger
from shared.models.stickynotes import StickyNoteORM, StickyNote

logger = get_logger(f"stickynotes.{__name__}")

router = APIRouter()

@router.get("/list", response_model=list[StickyNote])
async def list_sticky_notes(
    user_id: str = Query(..., description="The ID of the user whose sticky notes to list."),
    db: Session = Depends(get_db)
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