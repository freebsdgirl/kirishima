"""
Schemas for StickyNote creation and response.

This module defines Pydantic models for validating and serializing sticky note data:
- StickyNoteCreate: Used for creating new sticky notes, including validation for due date and periodicity.
- StickyNoteResponse: Used for API responses after sticky note creation.

Fields:
    - text: The content of the sticky note.
    - due: Optional naive datetime (localtime) for when the note is due.
    - periodicity: Optional ISO 8601 repeating interval string (e.g., 'R/P1D').
    - user_id: Optional user identifier.

Validators:
    - due must be a naive datetime (not timezone-aware).
    - periodicity must match ISO 8601 repeating interval format.
"""
from pydantic import BaseModel, Field, validator
from typing import Optional
from datetime import datetime
import re

ISO8601_REPEAT_PATTERN = re.compile(r"^R(\d*)/(P.*)")

class StickyNoteCreate(BaseModel):
    text: str = Field(..., description="The content of the sticky note.")
    due: datetime = Field(..., description="The due date for the sticky note in ISO 8601 format (localtime, not UTC).")
    periodicity: Optional[str] = Field(
        None,
        description="The periodicity of the sticky note as an ISO 8601 repeating interval (e.g., 'R/P1D' for daily)."
    )
    user_id: Optional[str] = Field(None, description="The ID of the user who created the sticky note.")

    @validator("due")
    def due_must_be_naive(cls, v):
        if v is not None and v.tzinfo is not None:
            raise ValueError("due must be a naive (localtime) datetime, not UTC or timezone-aware.")
        return v

    @validator("periodicity")
    def periodicity_must_be_iso8601_repeat(cls, v):
        if v is not None and not ISO8601_REPEAT_PATTERN.match(v):
            raise ValueError("periodicity must be a valid ISO 8601 repeating interval (e.g., 'R/P1D').")
        return v

class StickyNoteResponse(BaseModel):
    status: str
    id: str
