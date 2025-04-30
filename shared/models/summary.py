"""
This module defines data models for representing summaries and their associated metadata.
Classes:
    SummaryType (Enum): Enumerates standard summary categorizations, such as time of day (morning, afternoon, evening) and frequency-based intervals (daily, weekly, monthly, periodic).
    SummaryMetadata (BaseModel): Captures metadata for a summary, including time range, summary type, and optional keywords for contextual tagging and filtering.
    Summary (BaseModel): Represents a summary with a unique identifier, content, and optional metadata for temporal and contextual tracking.
These models are designed for structured organization, filtering, and analysis of summary data, leveraging Pydantic for data validation and serialization.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

from uuid import uuid4


class SummaryType(str, Enum):
    """
    Enum representing different types of summary periods or intervals.
    
    Defines standard summary categorizations including time of day (morning, afternoon, evening)
    and frequency-based summaries (daily, weekly, monthly, periodic).
    
    Useful for categorizing and filtering summaries based on their temporal characteristics.
    """
    MORNING = "morning"
    AFTERNOON = "afternoon"
    EVENING = "evening"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    PERIODIC = "periodic"


class SummaryMetadata(BaseModel):
    """
    Represents metadata associated with a summary, capturing temporal and contextual details.
    
    Provides structured information about a summary's time range, type, and associated keywords.
    Useful for organizing, filtering, and analyzing summaries based on their metadata attributes.
    
    Attributes:
        timestamp_begin (str): Start timestamp indicating when the summary period begins.
        timestamp_end (str): End timestamp indicating when the summary period concludes.
        summary_type (SummaryType): Categorization of the summary by time interval or frequency.
        keywords (Optional[List[str]], optional): List of keywords that describe or tag the summary content.
        user_id (Optional[str], optional): Unique identifier of the user associated with the summary.
    """
    timestamp_begin: str                = Field(..., description="Start timestamp of the summary")
    timestamp_end: str                  = Field(..., description="End timestamp of the summary")
    summary_type: SummaryType           = Field(..., description="Type of the summary (e.g., daily, weekly)")
    keywords: Optional[List[str]]       = Field(None, description="List of keywords associated with the summary") 
    user_id: Optional[str]              = Field(None, description="User ID associated with the summary")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "timestamp_begin": "2023-10-01T00:00:00Z",
                    "timestamp_end": "2023-10-31T23:59:59Z",
                    "summary_type": SummaryType.MONTHLY,
                    "keywords": ["October", "2023", "monthly summary"],
                    "user_id": "123e4567-e89b-12d3-a456-426614174000"
                },
                {
                    "timestamp_begin": "2023-10-01T08:00:00Z",
                    "timestamp_end": "2023-10-01T12:00:00Z",
                    "summary_type": SummaryType.MORNING,
                    "keywords": ["morning", "daily"],
                    "user_id": "123e4567-e89b-12d3-a456-426614174001"
                }
            ]
        }
    }


class Summary(BaseModel):
    """
    Represents a comprehensive summary with a unique identifier, content, and optional metadata.
    
    Provides a structured model for capturing summary information, including its unique ID,
    textual content, and associated metadata for temporal and contextual tracking.
    
    Attributes:
        id (str): A unique identifier generated using UUID, defaulting to a new UUID if not specified.
        content (str): The main textual content of the summary.
        metadata (Optional[SummaryMetadata]): Optional metadata providing additional context 
            about the summary's time range, type, and keywords.
    """
    id: str                             = Field(default_factory=lambda: str(uuid4()), description="Unique identifier for the summary")
    content: str                        = Field(..., description="Content of the summary")
    metadata: Optional[SummaryMetadata] = Field(None, description="Metadata associated with the summary")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "content": "This is a summary of the events that occurred in October 2023.",
                    "metadata": {
                        "timestamp_begin": "2023-10-01T00:00:00Z",
                        "timestamp_end": "2023-10-31T23:59:59Z",
                        "summary_type": SummaryType.MONTHLY,
                        "keywords": ["October", "2023", "monthly summary"],
                        "user_id": "123e4567-e89b-12d3-a456-426614174000"
                    }
                },
                {
                    "id": "123e4567-e89b-12d3-a456-426614174001",
                    "content": "This is a summary of the morning events on October 1, 2023.",
                    "metadata": {
                        "timestamp_begin": "2023-10-01T08:00:00Z",
                        "timestamp_end": "2023-10-01T12:00:00Z",
                        "summary_type": SummaryType.MORNING,
                        "keywords": ["morning", "daily"],
                        "user_id": "123e4567-e89b-12d3-a456-426614174001"
                    }
                }
            ]
        }
    }


class SummaryCreateRequest(BaseModel):
    """
    Represents a request to create a summary with a specified time period and optional date.
    
    Allows clients to request a summary by defining the time period (day, week, month)
    and optionally specifying a specific date. If no date is provided, the current date 
    will be used as the default.
    
    Attributes:
        period (str): The time period for the summary, such as 'day', 'week', or 'month'.
        date (Optional[str]): The date in YYYY-MM-DD format. Defaults to today if not specified.
    """
    period: str                         = Field(..., description="Time period for the summary (e.g., 'day', 'week', 'month')")
    date: Optional[str]                 = Field(None, description="Date in YYYY-MM-DD format. Defaults to today if not provided.")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "period": "day",
                    "date": "2023-10-01"
                },
                {
                    "period": "week"
                }
            ]
        }
    }