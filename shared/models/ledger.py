"""
This module defines Pydantic models for the ledger system, supporting user messages, conversations, summaries, memories, topics, and related operations.
Models include:
- Raw and canonical representations of user and conversation messages for various platforms.
- Summary models for storing, creating, combining, and querying summaries over different periods (daily, weekly, monthly, etc.).
- Memory models for storing, searching, deduplicating, and scoring memories, including heatmap-based relevance.
- Topic models for creating, updating, and retrieving topics associated with memories.
- Request and response models for API endpoints, supporting flexible filtering, pagination, and batch operations.
These models are designed for use in a multi-platform conversational assistant, enabling structured storage, retrieval, and analysis of user interactions and contextual information.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from enum import Enum
from datetime import datetime
from uuid import uuid4


class RawUserMessage(BaseModel):
    """
    Represents a raw user message exchanged between a user and the system.

    Attributes:
        user_id (str): Sender's unique ID.
        platform (str): Origin platform (e.g., 'api', 'discord', etc).
        platform_msg_id (Optional[str]): Optional platform-specific message ID.
        role (str): Role of the message sender, either 'user' or 'assistant'.
        content (str): Message body.
        model (Optional[str]): Model/mode used for this message (e.g., 'default', 'nsfw').
        tool_calls (Optional[dict]): Tool call requests as dict/JSON.
        function_call (Optional[dict]): Function call content as dict/JSON.
    """
    user_id: str                                = Field(..., description="Sender's unique ID")
    platform: str                               = Field(..., description="Origin platform ('api','discord',etc)")
    platform_msg_id: Optional[str]              = Field(None, description="Optional platform‑specific message ID")
    role: str                                   = Field(..., description="'user' or 'assistant'")
    content: str                                = Field(..., description="Message body")
    model: Optional[str]                        = Field(None, description="Model/mode used for this message (e.g., 'default', 'nsfw')")
    tool_calls: Optional[dict]                  = Field(None, description="Tool call requests as dict/JSON")
    function_call: Optional[dict]               = Field(None, description="Function call content as dict/JSON")
    tool_call_id: Optional[str]                 = Field(None, description="Tool call ID for tool messages")

    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": "1234567890",
                "platform": "discord",
                "platform_msg_id": "9876543210",
                "role": "user",
                "content": "Hello, how are you?",
                "model": "default",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": "{\"location\": \"New York\"}"
                        }
                    }
                ],
                "function_call": {
                    "name": "get_weather",
                    "arguments": "{\"location\": \"New York\"}"
                }
            }
        }
    }


class CanonicalUserMessage(BaseModel):
    """
    Represents a canonical user message exchanged between a user and an assistant.

    Attributes:
        id (int): Unique message ID.
        user_id (str): Sender's unique identifier.
        platform (str): Origin platform (e.g., 'api', 'discord').
        platform_msg_id (Optional[str]): Optional platform-specific message ID.
        role (str): Role of the message sender ('user' or 'assistant').
        content (str): Message body content.
        created_at (str): Timestamp when the message was created.
        updated_at (str): Timestamp when the message was last updated.
        model (Optional[str]): Model/mode used for this message (e.g., 'default', 'nsfw').
        tool_calls (Optional[dict]): Tool call requests as dict/JSON.
        function_call (Optional[dict]): Function call content as dict/JSON.
    """
    id: int                                     = Field(..., description="Unique message ID")
    user_id: str                                = Field(..., description="Sender's unique ID")
    platform: str                               = Field(..., description="Origin platform ('api','discord',etc)")
    platform_msg_id: Optional[str]              = Field(None, description="Optional platform‑specific message ID")
    role: str                                   = Field(..., description="'user' or 'assistant'")
    content: str                                = Field(..., description="Message body")
    model: Optional[str]                        = Field(None, description="Model/mode used for this message (e.g., 'default', 'nsfw')")
    tool_calls: Optional[dict]                  = Field(None, description="Tool call requests as dict/JSON")
    function_call: Optional[dict]               = Field(None, description="Function call content as dict/JSON")
    tool_call_id: Optional[str]                 = Field(None, description="Tool call ID for tool messages")
    created_at: str                             = Field(..., description="Message creation timestamp")
    updated_at: str                             = Field(..., description="Message update timestamp")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 1,
                "user_id": "1234567890",
                "platform": "discord",
                "platform_msg_id": "9876543210",
                "role": "user",
                "content": "Hello, how are you?",
                "model": "default",
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": "{\"location\": \"New York\"}"
                        }
                    }
                ],
                "function_call": {
                    "name": "get_weather",
                    "arguments": "{\"location\": \"New York\"}"
                },
                "created_at": "2023-10-01 12:00:00Z",
                "updated_at": "2023-10-01 12:00:00Z"
            }
        }
    }


class RawConversationMessage(BaseModel):
    """
    Represents a raw message within a conversation, typically used for storing or processing messages from various platforms.

    Attributes:
        conversation_id (str): Discord channel or thread ID associated with the message.
        platform (str): Origin platform of the message (e.g., 'api', 'discord').
        role (str): Role of the message sender, either 'user' or 'assistant'.
        content (str): The body of the message.
    """
    conversation_id: str                        = Field(..., description="Discord channel / thread ID")
    platform: str                               = Field(..., description="Origin platform ('api','discord',etc)")
    role: str                                   = Field(..., description="'user' or 'assistant'")
    content: str                                = Field(..., description="Message body")

    model_config = {
        "json_schema_extra": {
            "example": {
                "conversation_id": "1234567890",
                "platform": "discord",
                "role": "user",
                "content": "Hello, how are you?"
            }
        }
    }


class CanonicalConversationMessage(BaseModel):
    """
    Represents a canonical message within a conversation, typically used for storing and retrieving messages
    from various platforms (e.g., Discord, API).

    Attributes:
        id (int): Unique message ID.
        conversation_id (str): Discord channel or thread ID associated with the message.
        platform (str): Origin platform of the message (e.g., 'api', 'discord').
        role (str): Role of the message sender, either 'user' or 'assistant'.
        content (str): The body of the message.
        created_at (str): Timestamp indicating when the message was created.
        updated_at (str): Timestamp indicating when the message was last updated.
    """
    id: int                                     = Field(..., description="Unique message ID")
    conversation_id: str                        = Field(..., description="Discord channel / thread ID")
    platform: str                               = Field(..., description="Origin platform ('api','discord',etc)")
    role: str                                   = Field(..., description="'user' or 'assistant'")
    content: str                                = Field(..., description="Message body")
    created_at: str                             = Field(..., description="Message creation timestamp")
    updated_at: str                             = Field(..., description="Message update timestamp")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 1,
                "conversation_id": "1234567890",
                "platform": "discord",
                "role": "user",
                "content": "Hello, how are you?",
                "created_at": "2023-10-01T12:00:00Z",
                "updated_at": "2023-10-01T12:00:00Z"
            }
        }
    }


class DeleteSummary(BaseModel):
    """
    Represents a summary of a delete operation, tracking the number of rows deleted.
    
    Attributes:
        deleted (int): The total number of rows that were successfully deleted during the operation.
    """
    deleted: int                                = Field(..., description="Number of rows deleted")

    model_config = {
        "json_schema_extra": {
            "example": {
                "deleted": 5
            }
        }
    }

# --- Summary Models (moved from shared/models/summary.py) ---
class SummaryType(str, Enum):
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
    SummaryMetadata represents metadata information for a summary period.

    Attributes:
        timestamp_begin (str): Start timestamp of the summary.
        timestamp_end (str): End timestamp of the summary.
        summary_type (SummaryType): Type of the summary (e.g., daily, weekly).
    """
    timestamp_begin: str                = Field(..., description="Start timestamp of the summary")
    timestamp_end: str                  = Field(..., description="End timestamp of the summary")
    summary_type: SummaryType           = Field(..., description="Type of the summary (e.g., daily, weekly)")
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "timestamp_begin": "2023-10-01T00:00:00Z",
                    "timestamp_end": "2023-10-31T23:59:59Z",
                    "summary_type": SummaryType.MONTHLY
                },
                {
                    "timestamp_begin": "2023-10-01 08:00:00Z",
                    "timestamp_end": "2023-10-01 12:00:00Z",
                    "summary_type": SummaryType.MORNING
                }
            ]
        }
    }

class Summary(BaseModel):
    """
    Represents a summary entry with associated metadata.

    Attributes:
        id (str): Unique identifier for the summary. Automatically generated if not provided.
        content (str): Content of the summary.
        metadata (Optional[SummaryMetadata]): Metadata associated with the summary, such as time range and summary type.
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
                        "summary_type": SummaryType.MONTHLY
                    }
                },
                {
                    "id": "123e4567-e89b-12d3-a456-426614174001",
                    "content": "This is a summary of the morning events on October 1, 2023.",
                    "metadata": {
                        "timestamp_begin": "2023-10-01 08:00:00Z",
                        "timestamp_end": "2023-10-01 12:00:00Z",
                        "summary_type": SummaryType.MORNING
                    }
                }
            ]
        }
    }

class SummaryCreateRequest(BaseModel):
    """
    Represents a request to create a summary for a specific time period.
    
    Attributes:
        period (List[str]): Time periods for the summary, such as 'daily', 'weekly', or 'monthly'.
        date (str): Starting date for the summary in YYYY-MM-DD format. 
                    Defaults to the current date if not specified.
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
    Request model for combining multiple summaries into a single summary.

    Attributes:
        summaries (List[Summary]): List of summary objects to be combined.
        max_tokens (int): Maximum number of tokens allowed for the combined summary.
        user_alias (Optional[str]): Optional alias representing the user requesting the combination.
    """
    summaries: List[Summary]        = Field(..., description="List of summaries to be combined")
    max_tokens: int                 = Field(..., description="Maximum number of tokens for the combined summary")
    user_alias: Optional[str]       = Field(None, description="User alias for the summary")
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
                                "summary_type": SummaryType.MONTHLY
                            }
                        },
                        {
                            "id": "123e4567-e89b-12d3-a456-426614174001",
                            "content": "This is a summary of the morning events on October 1, 2023.",
                            "metadata": {
                                "timestamp_begin": "2023-10-01 08:00:00Z",
                                "timestamp_end": "2023-10-01 12:00:00Z",
                                "summary_type": SummaryType.MORNING
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
    SummaryRequest is a Pydantic model representing a request to summarize a list of user messages.

    Attributes:
        messages (List[CanonicalUserMessage]): 
            List of user messages to be summarized.
        user_alias (Optional[str]): 
            Optional alias for the user in the conversation.
        max_tokens (int): 
            Maximum number of tokens allowed for the generated summary.
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


class MemorySearchParams(BaseModel):
    """
    Parameters for searching memories in the ledger. Multiple parameters can be combined
    to filter results (AND logic - all specified parameters must match).

    Attributes:
        keywords (Optional[List[str]]): List of keywords to search for.
        category (Optional[str]): Category to search for.
        topic_id (Optional[str]): The topic ID to search for.
        memory_id (Optional[str]): Memory ID to search for (if provided, other filters are ignored).
        min_keywords (int): Minimum number of matching keywords required when searching by keywords.
        created_after (Optional[str]): Return memories created after this timestamp (ISO format).
        created_before (Optional[str]): Return memories created before this timestamp (ISO format).
    """
    keywords: Optional[List[str]]   = Field(None, description="List of keywords to search for.")
    category: Optional[str]         = Field(None, description="Category to search for.")
    topic_id: Optional[str]         = Field(None, description="The topic ID to search for.")
    memory_id: Optional[str]        = Field(None, description="Memory ID to search for (if provided, other filters are ignored).")
    min_keywords: int               = Field(2, description="Minimum number of matching keywords required when searching by keywords.")
    created_after: Optional[str]    = Field(None, description="Return memories created after this timestamp (ISO format).")
    created_before: Optional[str]   = Field(None, description="Return memories created before this timestamp (ISO format).")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "keywords": ["meeting", "project"],
                    "category": "Work",
                    "topic_id": None,
                    "memory_id": None,
                    "min_keywords": 2,
                    "created_after": "2025-07-01T00:00:00",
                    "created_before": "2025-07-31T23:59:59"
                }
            ]
        }
    }

class MemoryEntry(BaseModel):
    """
    Unified memory model that can represent any memory state.
    All fields are optional to support various use cases:
    - Creation: only memory, keywords, category needed
    - Search results: may include partial data
    - Full retrieval: includes all available data
    - Updates: only changed fields needed

    Attributes:
        id (Optional[str]): The unique identifier of the memory.
        memory (Optional[str]): The memory text content.
        created_at (Optional[str]): When the memory was created, ISO format.
        access_count (Optional[int]): Number of times this memory has been accessed.
        last_accessed (Optional[str]): When the memory was last accessed, ISO format.
        keywords (Optional[List[str]]): List of keywords associated with the memory.
        category (Optional[str]): The category of the memory.
        topic_id (Optional[str]): Associated topic ID.
        topic_name (Optional[str]): Associated topic name (for convenience, not stored).
    """
    id: Optional[str]               = Field(None, description="The unique identifier of the memory")
    memory: Optional[str]           = Field(None, description="The memory text content")
    created_at: Optional[str]       = Field(None, description="When the memory was created, ISO format")
    access_count: Optional[int]     = Field(0, description="Number of times this memory has been accessed")
    last_accessed: Optional[str]    = Field(None, description="When the memory was last accessed, ISO format")
    keywords: Optional[List[str]]   = Field(None, description="List of keywords associated with the memory")
    category: Optional[str]         = Field(None, description="The category of the memory")
    topic_id: Optional[str]         = Field(None, description="Associated topic ID")
    topic_name: Optional[str]       = Field(None, description="Associated topic name (for convenience, not stored)")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "mem_123",
                    "memory": "Project kickoff meeting scheduled for Monday",
                    "created_at": "2025-07-17T10:30:00",
                    "access_count": 5,
                    "last_accessed": "2025-07-17T15:45:00",
                    "keywords": ["meeting", "project"],
                    "category": "Work",
                    "topic_id": "topic_456",
                    "topic_name": "Project Planning"
                },
                {
                    "memory": "Remember to buy groceries",
                    "keywords": ["groceries", "shopping"],
                    "category": "Personal"
                }
            ]
        }
    }

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "mem_123",
                    "memory": "Project kickoff meeting scheduled for Monday",
                    "created_at": "2025-07-17T10:30:00",
                    "access_count": 5,
                    "last_accessed": "2025-07-17T15:45:00",
                    "keywords": ["meeting", "project"],
                    "category": "Work"
                }
            ]
        }
    }


class TopicIDsTimeframeRequest(BaseModel):
    """
    Request model for retrieving topic IDs in a given time frame.

    Attributes:
        start (str): Start timestamp (YYYY-MM-DD HH:MM:SS[.sss])
        end (str): End timestamp (YYYY-MM-DD HH:MM:SS[.sss])
    """
    start: str                      = Field(..., description="Start timestamp (YYYY-MM-DD HH:MM:SS[.sss])")
    end: str                        = Field(..., description="End timestamp (YYYY-MM-DD HH:MM:SS[.sss])")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "start": "2023-10-01 00:00:00",
                    "end": "2023-10-31 23:59:59"
                },
                {
                    "start": "2023-10-01 08:00:00",
                    "end": "2023-10-01 12:00:00"
                }
            ]
        }
    }


class AssignTopicRequest(BaseModel):
    """
    Request model for assigning a topic within a specific time frame.

    Attributes:
        topic_id (Optional[str]): The ID of the topic to assign to messages.
        start (str): Start timestamp in ISO 8601 format (YYYY-MM-DD HH:MM:SS[.sss])
        end (str): End timestamp in ISO 8601 format (YYYY-MM-DD HH:MM:SS[.sss])
    """
    topic_id: Optional[str]         = Field(None, description="The ID of the topic to assign to messages")
    start: str                      = Field(..., description="Start timestamp in ISO 8601 format (YYYY-MM-DD HH:MM:SS[.sss])")
    end: str                        = Field(..., description="End timestamp in ISO 8601 format (YYYY-MM-DD HH:MM:SS[.sss])")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "topic_id": "memory_id_goes_here",
                    "start": "2023-10-01 00:00:00",
                    "end": "2023-10-31 23:59:59"
                },
                {
                    "topic_id": "memory_id_goes_here",
                    "start": "2023-10-01 08:00:00",
                    "end": "2023-10-01 12:00:00"
                }
            ]
        }
    }


class MemoryListRequest(BaseModel):
    """
    Request model for retrieving a list of memories based on search parameters.

    Attributes:
        limit (int): Maximum number of memories to return.
        offset (int): Offset for pagination.
    """
    limit: int          = Field(100, description="Maximum number of memories to return")
    offset: int         = Field(0, description="Offset for pagination")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "limit": 100,
                    "offset": 0
                }
            ]
        }
    }


class MemoryDedupRequest(BaseModel):
    """
    Request model for memory deduplication operations.

    Attributes:
        dry_run (bool): If True, only analyze and return what would be done without making changes.
        grouping_strategy (str): Strategy for grouping memories.
        min_keyword_matches (int): Minimum number of matching keywords for keyword_overlap strategy.
        timeframe_days (int): Number of days for timeframe grouping window.
    """
    dry_run: bool               = Field(False, description="If True, only analyze and return what would be done without making changes")
    grouping_strategy: str      = Field("topic_similarity", description="Strategy for grouping memories")
    min_keyword_matches: int    = Field(2, description="Minimum number of matching keywords for keyword_overlap strategy")
    timeframe_days: int         = Field(7, description="Number of days for timeframe grouping window")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "dry_run": True,
                    "grouping_strategy": "topic_similarity",
                    "min_keyword_matches": 2,
                    "timeframe_days": 7
                }
            ]
        }
    }


class MemoryDedupGroup(BaseModel):
    """
    Represents a group of memories for deduplication.

    Attributes:
        memory_ids (List[str]): List of memory IDs in this group.
        group_name (str): Descriptive name for this group.
    """
    memory_ids: List[str]        = Field(..., description="List of memory IDs in this group")
    group_name: str              = Field(..., description="Descriptive name for this group")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "memory_ids": ["mem_123", "mem_456", "mem_789"],
                    "group_name": "Project Planning Group"
                },
                {
                    "memory_ids": ["mem_101", "mem_102"],
                    "group_name": "Meeting Notes Group"
                }
            ]
        }
    }


class MemoryDedupResult(BaseModel):
    """
    Result of a memory deduplication operation for a single group.

    Attributes:
        status (str): Status of the operation.
        grouping_strategy (str): Strategy used for grouping.
        group (str): Name/description of the group processed.
        updated_memories (dict): Dictionary of memory IDs to their update data.
        deleted_memories (List[str]): List of memory IDs that were deleted.
    """
    status: str                 = Field(..., description="Status of the operation")
    grouping_strategy: str      = Field(..., description="Strategy used for grouping")
    group: str                  = Field(..., description="Name/description of the group processed")
    updated_memories: dict      = Field(default_factory=dict, description="Dictionary of memory IDs to their update data")
    deleted_memories: List[str] = Field(default_factory=list, description="List of memory IDs that were deleted")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "success",
                    "grouping_strategy": "topic_similarity",
                    "group": "Project Planning Group",
                    "updated_memories": {
                        "mem_123": {"memory": "Updated memory content", "keywords": ["project", "planning"]},
                        "mem_456": {"memory": "Another updated memory content", "keywords": ["meeting", "notes"]}
                    },
                    "deleted_memories": ["mem_789"]
                },
                {
                    "status": "partial_success",
                    "grouping_strategy": "keyword_overlap",
                    "group": "Meeting Notes Group",
                    "updated_memories": {
                        "mem_101": {"memory": "Updated meeting notes", "keywords": ["meeting", "notes"]},
                        "mem_102": {"memory": "Another updated note", "keywords": ["discussion"]}
                    },
                    "deleted_memories": []
                }
            ]
        }
    }


class MemoryDedupResponse(BaseModel):
    """
    Response model for memory deduplication operations.

    Attributes:
        status (str): Overall status of the operation.
        grouping_strategy (str): Strategy used for grouping.
        message (str): Descriptive message about the operation.
        results (Optional[List[MemoryDedupResult]]): List of deduplication results per group.
        dry_run_info (Optional[dict]): Information about what would be done in dry run mode.
    """
    status: str                                 = Field(..., description="Overall status of the operation")
    grouping_strategy: str                      = Field(..., description="Strategy used for grouping")
    message: str                                = Field(..., description="Descriptive message about the operation")
    results: Optional[List[MemoryDedupResult]]  = Field(None, description="List of deduplication results per group")
    dry_run_info: Optional[dict]                = Field(None, description="Information about what would be done in dry run mode")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "status": "success",
                    "grouping_strategy": "topic_similarity",
                    "message": "Memory deduplication completed successfully.",
                    "results": [
                        {
                            "status": "success",
                            "grouping_strategy": "topic_similarity",
                            "group": "Project Planning Group",
                            "updated_memories": {
                                "mem_123": {"memory": "Updated memory content", "keywords": ["project", "planning"]},
                                "mem_456": {"memory": "Another updated memory content", "keywords": ["meeting", "notes"]}
                            },
                            "deleted_memories": ["mem_789"]
                        }
                    ],
                    "dry_run_info": None
                }
            ]
        }
    }


class HeatmapKeyword(BaseModel):
    """
    Represents a keyword in the heatmap with its relevance score.
    
    Attributes:
        keyword (str): The keyword text.
        score (float): Current relevance score (0.0 to 1.0).
        last_updated (datetime): When this keyword was last updated.
    """
    keyword: str                = Field(..., description="The keyword text")
    score: float                = Field(..., ge=0.0, le=1.0, description="Current relevance score")
    last_updated: datetime      = Field(..., description="When this keyword was last updated")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "keyword": "project",
                    "score": 0.85,
                    "last_updated": "2023-10-01T12:00:00Z"
                }
            ]
        }
    }



class HeatmapMemory(BaseModel):
    """
    Represents a memory with its heatmap-calculated relevance score.
    
    Attributes:
        memory_id (str): Unique memory identifier.
        score (float): Calculated relevance score based on keyword matches.
        last_updated (datetime): When this score was last calculated.
    """
    memory_id: str                 = Field(..., description="Unique memory identifier")
    score: float                   = Field(..., ge=0.0, description="Calculated relevance score")
    last_updated: datetime         = Field(..., description="When this score was last calculated")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "memory_id": "mem_123",
                    "score": 0.75,
                    "last_updated": "2023-10-01T12:00:00Z"
                }
            ]
        }
    }


class HeatmapUpdateRequest(BaseModel):
    """
    Request model for updating the keyword heatmap.
        
    Attributes:
        keywords (Dict[str, str]): Dictionary mapping keywords to their weights ("high", "medium", "low").
    """
    keywords: Dict[str, str] = Field(..., description="Keyword -> weight mapping (high, medium, low)")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "keywords": {
                        "project": "high",
                        "meeting": "medium",
                        "deadline": "low"
                    }
                }
            ]
        }
    }


class HeatmapUpdateResponse(BaseModel):
    """
    Response model for heatmap update operations.
    
    Represents the result of a heatmap update, tracking changes to keywords and their associated memories.
    
    Attributes:
        success (bool): Indicates whether the heatmap update operation was successful.
        new_keywords (List[str]): Keywords that were newly added to the heatmap.
        updated_keywords (List[str]): Keywords that had their scores adjusted.
        decayed_keywords (List[str]): Keywords that were decayed due to non-mention.
        removed_keywords (List[str]): Keywords that were removed due to low scores.
        affected_memories (int): Number of memories that had their scores recalculated during the update.
    """
    success: bool                   = Field(..., description="Whether the operation was successful")
    new_keywords: List[str]         = Field(default_factory=list, description="Keywords that were newly added")
    updated_keywords: List[str]     = Field(default_factory=list, description="Keywords that had their scores adjusted")
    decayed_keywords: List[str]     = Field(default_factory=list, description="Keywords that were decayed due to non-mention")
    removed_keywords: List[str]     = Field(default_factory=list, description="Keywords that were removed due to low scores")
    affected_memories: int          = Field(..., description="Number of memories that had their scores recalculated")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "new_keywords": ["project", "meeting"],
                    "updated_keywords": ["deadline"],
                    "decayed_keywords": ["old_keyword"],
                    "removed_keywords": ["low_score_keyword"],
                    "affected_memories": 42
                }
            ]
        }
    }


class TopMemoriesResponse(BaseModel):
    """
    Response model representing a list of top memories with their detailed information.
    
    Attributes:
        memories (List[Dict]): A list of top memories, where each memory is a dictionary containing
        details such as memory ID, content, creation timestamp, access statistics, associated keywords,
        and category.
    
    Example:
        A response might include memories like a project kickoff meeting or a personal shopping reminder,
        each with unique metadata and contextual information.
    """
    memories: List[Dict] = Field(..., description="List of top memories with their details")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "memories": [
                        {
                            "id": "mem_123",
                            "memory": "Project kickoff meeting scheduled for Monday",
                            "created_at": "2025-07-17T10:30:00",
                            "access_count": 5,
                            "last_accessed": "2025-07-17T15:45:00",
                            "keywords": ["meeting", "project"],
                            "category": "Work"
                        },
                        {
                            "id": "mem_456",
                            "memory": "Remember to buy groceries",
                            "created_at": "2025-07-18T11:00:00",
                            "access_count": 2,
                            "last_accessed": "2025-07-18T12:00:00",
                            "keywords": ["groceries", "shopping"],
                            "category": "Personal"
                        }
                    ]
                }
            ]
        }
    }


class KeywordScoresResponse(BaseModel):
    """
    Response model representing keyword scores for contextual relevance.
        
    This model provides a mapping of keywords to their calculated relevance or importance scores.
    Scores are typically floating-point values between 0 and 1, indicating the significance 
    of each keyword in a given context.
    
    Attributes:
        scores (Dict[str, float]): A dictionary mapping keywords to their numerical relevance scores.
    
    Example:
        Scores might represent how relevant keywords are to a specific memory or context,
        with higher scores indicating greater importance or centrality.
    """
    scores: Dict[str, float] = Field(..., description="Mapping of keywords to their scores")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "scores": {
                        "project": 0.85,
                        "meeting": 0.75,
                        "deadline": 0.65
                    }
                }
            ]
        }
    }


class ContextMemoriesResponse(BaseModel):
    """
    Response model representing a list of contextual memory content strings.
    
    This model is used to return a collection of memory contents that are relevant 
    to a specific context or query. Each memory is represented as a plain text string.
    
    Attributes:
        memories (List[str]): A list of memory content strings extracted from the context.
    """
    memories: List[str] = Field(..., description="List of contextual memory content strings")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "memories": [
                        "Project kickoff meeting scheduled for Monday",
                        "Remember to buy groceries"
                    ]
                }
            ]
        }
    }


class TopicCreateRequest(BaseModel):
    """
    Request model for creating a new topic.
    
    This model defines the required information for creating a topic with a specified name.
    
    Attributes:
        name (str): The name of the topic to be created.
    """
    name: str   = Field(..., description="The name of the topic to create")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Project Planning"
                },
                {
                    "name": "Personal Reminders"
                }
            ]
        }
    }


class TopicResponse(BaseModel):
    """
    Response model representing a topic with its unique identifier and name.
    
    This model is used to return topic details, including the topic's unique ID and name.
    Useful for retrieving and displaying topic information in various contexts.
    
    Attributes:
        id (str): The unique identifier of the topic.
        name (str): The name of the topic.
    """
    id: str     = Field(..., description="The unique identifier of the topic")
    name: str   = Field(..., description="The name of the topic")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "topic_123",
                    "name": "Project Planning"
                },
                {
                    "id": "topic_456",
                    "name": "Personal Reminders"
                }
            ]
        }
    }


class TopicUpdateRequest(BaseModel):
    """
    Request model for updating a topic's name.
    
    This model is used to provide the new name when updating an existing topic.
    Useful for renaming topics in various contexts.
    
    Attributes:
        name (str): The new name to be assigned to the topic.
    """
    name: str = Field(..., description="The new name for the topic")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "name": "Updated Project Planning"
                },
                {
                    "name": "Updated Personal Reminders"
                }
            ]
        }
    }


class TopicByIdRequest(BaseModel):
    """
    Request model for retrieving a topic by its ID.
    
    Attributes:
        topic_id (str): The unique identifier of the topic to retrieve.
    """
    topic_id: str = Field(..., description="The unique identifier of the topic")


class TopicMessagesRequest(BaseModel):
    """
    Request model for retrieving messages associated with a topic.
    
    Attributes:
        topic_id (str): The unique identifier of the topic.
    """
    topic_id: str = Field(..., description="The unique identifier of the topic")


class TopicRecentRequest(BaseModel):
    """
    Request model for retrieving recent topics.
    
    Attributes:
        limit (Optional[int]): Maximum number of recent topics to return.
    """
    limit: Optional[int] = Field(None, description="Maximum number of recent topics to return")


class TopicDeleteRequest(BaseModel):
    """
    Request model for deleting a topic.
    
    Attributes:
        topic_id (str): The unique identifier of the topic to delete.
    """
    topic_id: str = Field(..., description="The unique identifier of the topic to delete")



# User message request models  
class UserMessagesRequest(BaseModel):
    """
    Request model for filtering and retrieving user messages for a specific user.
    
    Allows filtering user messages by user_id, time period, date, and specific timestamp ranges.
    Useful for querying messages within specific temporal contexts.
    
    Attributes:
        user_id (str): The unique identifier of the user whose messages are to be retrieved.
        period (Optional[str]): Time period filter (morning, afternoon, evening, night)
        date (Optional[str]): Date filter in YYYY-MM-DD format
        start (Optional[str]): Start timestamp filter
        end (Optional[str]): End timestamp filter
    """
    user_id: str = Field(..., description="The unique identifier of the user whose messages are to be retrieved.")
    period: Optional[str]   = Field(None, description="Time period filter (morning, afternoon, evening, night)")
    date: Optional[str]     = Field(None, description="Date filter in YYYY-MM-DD format")
    start: Optional[str]    = Field(None, description="Start timestamp filter")
    end: Optional[str]      = Field(None, description="End timestamp filter")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "user_id": "user-123",
                    "period": "morning",
                    "date": "2023-10-01",
                    "start": "2023-10-01 08:00:00",
                    "end": "2023-10-01 12:00:00"
                },
                {
                    "user_id": "user-456",
                    "period": "afternoon",
                    "date": "2023-10-01",
                    "start": "2023-10-01 12:00:00",
                    "end": "2023-10-01 18:00:00"
                }
            ]
        }
    }

class UserUntaggedMessagesRequest(BaseModel):
    """
    Request model for retrieving all untagged messages for a specific user.
    Attributes:
        user_id (str): The unique identifier of the user whose untagged messages are to be retrieved.
    """
    user_id: str

class UserLastMessageRequest(BaseModel):
    """
    Request model for retrieving the timestamp of the most recent message for a specific user.
    Attributes:
        user_id (str): The unique identifier of the user whose last message timestamp is to be retrieved.
    """
    user_id: str


class UserSyncRequest(BaseModel):
    """
    Request model for synchronizing user messages.
    
    Allows sending a list of raw user messages to be synchronized with the system.
    Useful for bulk message synchronization across different platforms and models.
    
    Attributes:
        user_id (str): The unique identifier of the user
        snapshot (List[RawUserMessage]): A list of raw user messages to synchronize
    """
    user_id: str = Field(..., description="The unique identifier of the user")
    snapshot: List[RawUserMessage] = Field(..., description="List of messages to synchronize")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "snapshot": [
                        {
                            "user_id": "123e4567-e89b-12d3-a456-426614174000",
                            "content": "This is a user message.",
                            "role": "user",
                            "platform": "api",
                            "model": "default",
                        }
                    ]
                }
            ]
        }
    }


class ToolSyncRequest(BaseModel):
    """
    Request model for synchronizing tool messages.

    Requires both the tool call itself as well as the tool output.
    Previously, this was logged in the UserSyncRequest, but it has been separated for clarity.

    Attributes:
        model (str): The model used for the tool
        platform (str): The platform used for the tool
        tool_call (str): The tool call to synchronize
        tool_output (str): The output from the tool call
    """
    model: str              = Field(..., description="The model used for the tool")
    platform: str           = Field(..., description="The platform used for the tool")
    tool_call: str          = Field(..., description="The tool call to synchronize")
    tool_output: str        = Field(..., description="The output from the tool call")
    tool_call_id: str       = Field(..., description="The unique identifier for the tool call")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "model": "example_model",
                    "platform": "example_platform",
                    "tool_call": "example_tool_call",
                    "tool_output": "example_tool_output",
                    "tool_call_id": "123e4567-e89b-12d3-a456-426614174000"
                }
            ]
        }
    }


class SummaryGetRequest(BaseModel):
    """
    Request model for retrieving summaries with flexible filtering options.
    
    Allows querying summaries based on various criteria such as ID, period, 
    timestamp range, keywords, and result limit.
    
    Attributes:
        id (Optional[str]): Unique identifier to filter a specific summary.
        period (Optional[str]): Period type to filter summaries (e.g., 'monthly').
        timestamp_begin (Optional[str]): Start timestamp for filtering summaries.
        timestamp_end (Optional[str]): End timestamp for filtering summaries.
        keywords (Optional[List[str]]): List of keywords to search within summary text.
        limit (Optional[int]): Maximum number of summaries to return in the query result.
    """
    id: Optional[str]               = Field(None, description="Filter by summary ID")
    period: Optional[str]           = Field(None, description="Filter summaries by summary period")
    timestamp_begin: Optional[str]  = Field(None, description="Lower bound for summary timestamp")
    timestamp_end: Optional[str]    = Field(None, description="Upper bound for summary timestamp")
    keywords: Optional[List[str]]   = Field(None, description="List of keywords to search for in summary text")
    limit: Optional[int]            = Field(None, description="Maximum number of summaries to return")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "period": "monthly",
                    "timestamp_begin": "2023-10-01 00:00:00Z",
                    "timestamp_end": "2023-10-31 23:59:59Z",
                    "keywords": ["meeting", "project"],
                    "limit": 10
                }
            ]
        }
    }


class SummaryDeleteRequest(BaseModel):
    """
    Request model for deleting summaries with flexible filtering options.
    
    Allows deleting summaries based on various criteria such as ID, period, 
    and timestamp range.
    
    Attributes:
        id (Optional[str]): Unique identifier to delete a specific summary.
        period (Optional[str]): Period type to filter summaries for deletion (e.g., 'monthly').
        timestamp_begin (Optional[str]): Start timestamp for deletion range.
        timestamp_end (Optional[str]): End timestamp for deletion range.
    """
    id: Optional[str]               = Field(None, description="Delete summary by ID")
    period: Optional[str]           = Field(None, description="Delete summaries by period type")
    timestamp_begin: Optional[str]  = Field(None, description="Lower bound for deletion timestamp range")
    timestamp_end: Optional[str]    = Field(None, description="Upper bound for deletion timestamp range")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "period": "monthly",
                    "timestamp_begin": "2023-10-01 00:00:00Z",
                    "timestamp_end": "2023-10-31 23:59:59Z"
                }
            ]
        }
    }


class MergeTopicsRequest(BaseModel):
    """
    Request model for merging multiple topics into a primary topic.
    
    Attributes:
        primary_id (str): The ID of the topic to keep.
        primary_name (Optional[str]): New name for the primary topic (optional).
        merge_ids (List[str]): List of topic IDs to merge into the primary topic.
    """
    primary_id: str = Field(..., description="ID of the topic to keep")
    primary_name: Optional[str] = Field(None, description="New name for the primary topic (optional)")
    merge_ids: List[str] = Field(..., description="List of topic IDs to merge into primary")


class DeleteUserMessagesRequest(BaseModel):
    """
    Request model for deleting user messages, optionally filtered by period and date.
    Attributes:
        user_id (str): The unique identifier of the user whose messages will be deleted.
        period (Optional[str]): Time period to filter messages.
        date (Optional[str]): Date in YYYY-MM-DD format.
    """
    user_id: str
    period: Optional[str] = None
    date: Optional[str] = None