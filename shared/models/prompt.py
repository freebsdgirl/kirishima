"""
This module defines the BuildSystemPrompt Pydantic model, which encapsulates the configuration required for constructing a prompt in a conversational system.
Classes:
    BuildSystemPrompt: Represents the parameters for building a prompt, including optional memory entries, conversation mode, platform, summaries, and username.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from shared.models.memory import MemoryEntryFull


class BuildSystemPrompt(BaseModel):
    """
    A Pydantic model representing the configuration for building a prompt.
    
    Attributes:
        memories (Optional[List[MemoryEntryFull]]): Optional list of memory entries used in prompt construction.
        mode (str): The mode of the conversation, required parameter.
        platform (str): The platform of the conversation, required parameter.
        summaries (Optional[str]): Optional list of summaries to include in the prompt.
        username (Optional[str]): Optional username of the user associated with the prompt.
        timestamp (str): Optional timestamp of the request.
    """
    memories: Optional[List[MemoryEntryFull]]   = Field(None, description="List of memory entries")
    mode: str                                   = Field(..., description="Mode of the conversation")
    platform: str                               = Field(..., description="Platform of the conversation")
    summaries: Optional[str]                    = Field(None, description="List of summaries")
    username: Optional[str]                     = Field(None, description="Username of the user")
    timestamp: str                              = Field(None, description="Timestamp of the request")

    model_config = {
        "json_schema_extra": {
            "example": {
                "memories": [
                    {
                        "id": "memory_id_1",
                        "content": "This is a memory entry."
                    }
                ],
                "mode": "chat",
                "platform": "web",
                "summaries": ["summary1", "summary2"],
                "username": "user123",
                "timestamp": "2023-10-01T12:00:00Z"
            }
        }
    }
    