"""
This module defines Pydantic models for representing and managing user and conversation messages,
summaries, and deletion requests within a multi-platform communication system (e.g., API, Discord).
Models included:
- RawUserMessage: Raw user message exchanged between a user and the system.
- CanonicalUserMessage: Canonical form of a user message with metadata.
- RawConversationMessage: Raw message within a conversation, for storage or processing.
- CanonicalConversationMessage: Canonical conversation message with metadata.
- DeleteSummary: Summary of a delete operation, tracking number of rows deleted.
- UserSummary: Summary of messages for a specific user.
- UserSummaryList: List of user message summaries.
- DeleteRequest: Request to delete records by their unique identifiers.
- ConversationSummary: Summary of messages for a specific conversation.
- ConversationSummaryList: List of conversation summaries.
- SummaryRequest: Request to generate a summary of user messages.
Each model leverages Pydantic's BaseModel for data validation and serialization, and includes
detailed field descriptions for clarity and documentation purposes.
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class RawUserMessage(BaseModel):
    """
    Represents a raw user message exchanged between a user and the system.

    Attributes:
        user_id (str): Sender's unique ID.
        platform (str): Origin platform (e.g., 'api', 'discord', etc).
        platform_msg_id (Optional[str]): Optional platform-specific message ID.
        role (str): Role of the message sender, either 'user' or 'assistant'.
        content (str): Message body.
    """
    user_id: str                                = Field(..., description="Sender's unique ID")
    platform: str                               = Field(..., description="Origin platform ('api','discord',etc)")
    platform_msg_id: Optional[str]              = Field(None, description="Optional platform‑specific message ID")
    role: str                                   = Field(..., description="'user' or 'assistant'")
    content: str                                = Field(..., description="Message body")


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
    """
    id: int                                     = Field(..., description="Unique message ID")
    user_id: str                                = Field(..., description="Sender's unique ID")
    platform: str                               = Field(..., description="Origin platform ('api','discord',etc)")
    platform_msg_id: Optional[str]              = Field(None, description="Optional platform‑specific message ID")
    role: str                                   = Field(..., description="'user' or 'assistant'")
    content: str                                = Field(..., description="Message body")
    created_at: str                             = Field(..., description="Message creation timestamp")
    updated_at: str                             = Field(..., description="Message update timestamp")


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


class DeleteSummary(BaseModel):
    """
    Represents a summary of a delete operation, tracking the number of rows deleted.
    
    Attributes:
        deleted (int): The total number of rows that were successfully deleted during the operation.
    """
    deleted: int                                = Field(..., description="Number of rows deleted")


class UserSummary(BaseModel):
    """
    Represents a summary of messages for a specific user, capturing key details about their communication.
    
    Attributes:
        id (int): Unique identifier for the message summary.
        user_id (str): Unique identifier of the message sender.
        content (str): Condensed content of the summarized messages.
        level (int): Aggregation or significance level of the summarized messages.
        timestamp_begin (str): Start timestamp of the messages being summarized.
        timestamp_end (str): End timestamp of the messages being summarized.
        timestamp_summarized (str): Timestamp when the summary was created.
    """
    id: int                                     = Field(..., description="Unique message ID")
    user_id: str                                = Field(..., description="Sender's unique ID")
    content: str                                = Field(..., description="Summarized message content")
    level: int                                  = Field(..., description="Level of the summarized messages")
    timestamp_begin: str                        = Field(..., description="Start timestamp of the summarized messages")
    timestamp_end: str                          = Field(..., description="End timestamp of the summarized messages")
    timestamp_summarized: str                   = Field(..., description="Timestamp when the message was summarized")


class UserSummaryList(BaseModel):
    """
    Represents a list of user message summaries, containing multiple UserSummary instances.
    
    Attributes:
        summaries (List[UserSummary]): A collection of summarized user messages.
    """
    summaries: List[UserSummary]                = Field(..., description="List of summarized messages")


class DeleteRequest(BaseModel):
    """
    Represents a request to delete records by their unique identifiers.
    
    Attributes:
        ids (List[int]): A list of integer IDs to be deleted. Must contain at least one ID.
    """
    ids: List[int]                              = Field(..., min_items=1, description="IDs to delete")


class ConversationSummary(BaseModel):
    """
    Represents a summary of messages for a specific conversation, capturing key details about the communication.
    
    Attributes:
        id (int): Unique identifier for the message summary.
        conversation_id (str): Discord channel or thread identifier.
        content (str): Condensed content of the summarized messages.
        period (str): Aggregation period (daily, weekly, or monthly).
        timestamp_begin (str): Start timestamp of the messages being summarized.
        timestamp_end (str): End timestamp of the messages being summarized.
        timestamp_summarized (str): Timestamp when the summary was created.
    """
    id: int                                     = Field(..., description="Unique message ID")
    conversation_id: str                        = Field(..., description="Discord channel / thread ID")
    content: str                                = Field(..., description="Summarized message content")
    period: str                                 = Field(..., description="daily, weekly, or monthly")
    timestamp_begin: str                        = Field(..., description="Start timestamp of the summarized messages")
    timestamp_end: str                          = Field(..., description="End timestamp of the summarized messages")
    timestamp_summarized: str                   = Field(..., description="Timestamp when the message was summarized")


class ConversationSummaryList(BaseModel):
    """
    Represents a list of conversation summaries, containing multiple ConversationSummary instances.
        
    Attributes:
        summaries (List[ConversationSummary]): A collection of summarized conversation messages.
    """
    summaries: List[ConversationSummary]        = Field(..., description="List of summarized messages")


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

class CombinedSummaryRequest(BaseModel):
    """
    Represents a request to generate a combined summary of user summaries.
    
    Attributes:
        summaries (List[UserSummary]): A list of user message summaries to be combined.
        user_alias (Optional[str]): An optional alias for the user in the conversation.
        max_tokens (int): The maximum number of tokens allowed for the generated summary.
    """
    summaries: List[UserSummary]                = Field(..., description="List of summarized messages")
    user_alias: Optional[str]                   = Field(None, description="Alias for the user in the conversation")
    max_tokens: int                             = Field(..., description="Maximum number of tokens for the summary")