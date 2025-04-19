"""
This module provides functionality to build a structured prompt for guest messages
by processing conversation context and incoming message details.
Functions:
    - build_prompt(request: ProxyRequest) -> str:
        Constructs a formatted prompt string using the context and message details
        from the provided ProxyRequest object.
Classes:
    - ProxyRequest (imported from shared.models.proxy):
        Represents the proxy request containing message and context details.
Dependencies:
    - re: Used for regular expression operations to clean up the context string.
    - ProxyRequest: A model representing the structure of the proxy request.
"""

from shared.models.proxy import ProxyRequest
from app.util import create_memory_str
import re


def build_prompt(request: ProxyRequest) -> str:
    """
    Builds a prompt for a guest message, processing the conversation context and preparing a structured message template.
    
    Args:
        request (ProxyRequest): The proxy request containing message and context details.
    
    Returns:
        str: A formatted prompt string with conversation context and incoming message.
    """
    joined_memories = create_memory_str(request.memories or [])
    decoded_context = request.context.encode('utf-8').decode('unicode_escape')
    context = re.sub(r'^"|"$', '', decoded_context)
    prompt = f"""You are responding to a message over {request.message.platform} from a user that is not Randi.

Do not divulge any personal information about Randi.



[ PREVIOUS CONVERSATION ]

{context}

[ END OF PREVIOUS CONVERSATION ]



[ INCOMING MESSAGE at {request.message.timestamp} ]

{request.message.text}
"""

    return prompt
