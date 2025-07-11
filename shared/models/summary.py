"""
This module defines models for handling summaries and related requests using Pydantic for data validation.
Classes:
    SummaryType (Enum):
        Enum representing different types of summary periods or intervals, such as morning, daily, or monthly.
    SummaryMetadata (BaseModel):
        Represents metadata associated with a summary, including temporal and contextual details.
    Summary (BaseModel):
    SummaryCreateRequest (BaseModel):
    CombinedSummaryRequest (BaseModel):
        Represents a request to combine multiple summaries into a single summary with a token limit.
    SummaryRequest (BaseModel):
        Represents a request to generate a summary of user messages, including a maximum token limit.
Modules:
    shared.models.ledger:
        Contains the CanonicalUserMessage model used in the SummaryRequest class.
    uuid4 (function):
        Generates unique identifiers for summaries.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime

from shared.models.ledger import CanonicalUserMessage

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
    NIGHT = "night"
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
                    "timestamp_begin": "2023-10-01 08:00:00Z",
                    "timestamp_end": "2023-10-01 12:00:00Z",
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
                        "timestamp_begin": "2023-10-01 00:00:00Z",
                        "timestamp_end": "2023-10-31 23:59:59Z",
                        "summary_type": SummaryType.MONTHLY,
                        "keywords": ["October", "2023", "monthly summary"],
                        "user_id": "123e4567-e89b-12d3-a456-426614174000"
                    }
                },
                {
                    "id": "123e4567-e89b-12d3-a456-426614174001",
                    "content": "This is a summary of the morning events on October 1, 2023.",
                    "metadata": {
                        "timestamp_begin": "2023-10-01 08:00:00Z",
                        "timestamp_end": "2023-10-01 12:00:00Z",
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
        period (List[str]): The time period for the summary, such as 'daily', 'weekly', or 'monthly'.
        date (Optional[str]): The starting date in YYYY-MM-DD format.
    """
    period: List[str]               = Field(..., description="Time period for the summary (e.g., 'daily', 'weekly', 'monthly')")
    date: str                       = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"), description="Starting date in YYYY-MM-DD format.")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "period": ["daily"],
                    "date": "2023-10-01"
                },
                {
                    "period": ["weekly"],
                    "date": "2023-10-01"
                }
            ]
        }
    }


class CombinedSummaryRequest(BaseModel):
    """
    Represents a request to combine multiple summaries into a single summary.
    
    This model allows for aggregating multiple summaries with a specified maximum token limit
    and an optional user alias.
    
    Attributes:
        summaries (List[Summary]): A list of summaries to be combined.
        max_tokens (int): The maximum number of tokens allowed for the combined summary.
        user_alias (Optional[str], optional): An optional alias for the user creating the combined summary.
    """
    summaries: List[Summary] = Field(..., description="List of summaries to be combined")
    max_tokens: int = Field(..., description="Maximum number of tokens for the combined summary")
    user_alias: Optional[str] = Field(None, description="User alias for the summary")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "summaries": [
                        {
                            "id": "123e4567-e89b-12d3-a456-426614174000",
                            "content": "This is a summary of the events that occurred in October 2023.",
                            "metadata": {
                                "timestamp_begin": "2023-10-01 00:00:00Z",
                                "timestamp_end": "2023-10-31 23:59:59Z",
                                "summary_type": SummaryType.MONTHLY,
                                "keywords": ["October", "2023", "monthly summary"],
                                "user_id": "123e4567-e89b-12d3-a456-426614174000"
                            }
                        },
                        {
                            "id": "123e4567-e89b-12d3-a456-426614174001",
                            "content": "This is a summary of the morning events on October 1, 2023.",
                            "metadata": {
                                "timestamp_begin": "2023-10-01 08:00:00Z",
                                "timestamp_end": "2023-10-01 12:00:00Z",
                                "summary_type": SummaryType.MORNING,
                                "keywords": ["morning", "daily"],
                                "user_id": "123e4567-e89b-12d3-a456-426614174001"
                            }
                        }
                    ],
                    "max_tokens": 100,
                    "user_alias": "User123"
                }
            ]
        }
    }


class SummaryRequest(BaseModel):
    """
    Represents a request to generate a summary of user messages.
    
    Attributes:
        messages (List[CanonicalUserMessage]): A list of user messages to be summarized.
        user_alias (Optional[str]): An optional alias for the user in the conversation.
        max_tokens (int): The maximum number of tokens allowed for the generated summary.
    """
    messages: List[CanonicalUserMessage]        = Field(..., description="List of user messages to summarize")
    user_alias: Optional[str]                   = Field(None, description="Alias for the user in the conversation")
    max_tokens: int                             = Field(..., description="Maximum number of tokens for the summary")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "messages": [
                        {
                            "id": "123e4567-e89b-12d3-a456-426614174000",
                            "content": "This is a user message.",
                            "created_at": "2023-10-01 00:00:00Z",
                            "user_id": "123e4567-e89b-12d3-a456-426614174000"
                        },
                        {
                            "id": "123e4567-e89b-12d3-a456-426614174001",
                            "content": "This is another user message.",
                            "created_at": "2023-10-01 01:00:00Z",
                            "user_id": "123e4567-e89b-12d3-a456-426614174001"
                        }
                    ],
                    "user_alias": "User123",
                    "max_tokens": 100
                }
            ]
        }
    }

