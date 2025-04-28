"""
This module defines the BuildPrompt Pydantic model, which encapsulates the configuration required for constructing a prompt in a conversational system.
Classes:
    BuildPrompt: Represents the parameters for building a prompt, including optional memory entries, conversation mode, platform, summaries, and username.
    memories (Optional[List[MemoryEntryFull]]): An optional list of memory entries to be used in the prompt.
    mode (str): The mode of the conversation (required).
    platform (str): The platform on which the conversation takes place (required).
    summaries (Optional[str]): An optional list of summaries to include in the prompt.
    username (Optional[str]): The username associated with the prompt (optional).
    timestamp (str): An optional timestamp for the request.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from shared.models.chromadb import MemoryEntryFull


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
    