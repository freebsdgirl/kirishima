"""
This module defines the data models for sticky notes, including both the SQLAlchemy ORM model for database interactions
and the Pydantic model for data validation and serialization.

Classes:
    StatusEnum (enum.Enum): Enumeration of possible sticky note statuses ('active', 'snoozed', 'resolved').
    StickyNoteORM (Base): SQLAlchemy ORM model representing a sticky note in the database.
    StickyNote (BaseModel): Pydantic model for validating and serializing sticky note data.

Attributes:
    Base: Declarative base for SQLAlchemy models.
"""

from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.sqlite import TEXT
from sqlalchemy.sql import func
from sqlalchemy.types import Enum as SqlEnum
from sqlalchemy.orm import declarative_base
import enum
import uuid

Base = declarative_base()

class StatusEnum(str, enum.Enum):
    active = "active"
    snoozed = "snoozed"
    resolved = "resolved"

class StickyNoteORM(Base):
    __tablename__ = "stickynotes"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    text = Column(TEXT, nullable=False)
    status = Column(SqlEnum(StatusEnum), default=StatusEnum.active, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    user_id = Column(String, nullable=True)
    due = Column(DateTime(timezone=True), nullable=False)
    periodicity = Column(String, nullable=True)

class StickyNote(BaseModel):
    id: str = Field(..., description="The unique identifier for the sticky note.")
    text: str = Field(..., description="The content of the sticky note.")
    status: str = Field(..., description="The status of the sticky note (e.g., 'active', 'archived').")
    created_at: str = Field(..., description="The timestamp when the sticky note was created.")
    updated_at: Optional[str] = Field(None, description="The timestamp when the sticky note was last updated.")
    user_id: str = Field(..., description="The ID of the user who created the sticky note.")
    due: str = Field(..., description="The due date for the sticky note in ISO 8601 format. Localtime, not UTC.")
    periodicity: Optional[str] = Field(None, description="The periodicity of the sticky note (e.g., 'daily', 'weekly').")