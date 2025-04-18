"""
This module defines the IntentRequest data model, which represents a request with optional flags.

Classes:
    IntentRequest: A Pydantic model for handling intent requests, including conversation history and optional flags.

    message (List[ProxyMessage]): A list of ProxyMessage objects representing the conversation history.
    mode (Optional[bool]): A flag to check for a mode function. Defaults to False.
    memory (Optional[bool]): A flag to indicate whether memory functions should be used. Defaults to False.
"""

from pydantic import BaseModel
from typing import Optional, List
from shared.models.proxy import ProxyMessage

class IntentRequest(BaseModel):
    """
    IntentRequest is a data model representing a request with optional flags.

    Attributes:
        message (List[ProxyMessage]): A list of messages representing the conversation history.
        mode (Optional[bool]): A flag indicating to check for a mode function. Defaults to False.
        memory (Optional[bool]): A flag indicating whether to use memory functions. Defaults to False.
    """
    message: List[ProxyMessage] = []
    mode: Optional[bool] = False
    memory: Optional[bool] = False 