"""
This module defines data models for handling proxy requests and responses, as well as structured incoming messages. 
The models are built using Pydantic for data validation and serialization.
Classes:
    IncomingMessage:
    ProxyRequest:
        Useful for handling requests that involve user context and additional metadata.
    ProxyOneShotRequest:
        Includes parameters for model configuration, input prompt, and generation settings.
    ProxyResponse:
        Contains the generated response text, token usage, and timestamp of the response.
Usage:
    These models can be used to standardize the structure of incoming messages, proxy requests, 
    and responses in applications that involve communication platforms or language model interactions.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class IncomingMessage(BaseModel):
    """
    Represents a structured incoming message with platform-specific details.
    
    Captures essential information about a message, including its origin platform, 
    sender, content, timestamp, and optional metadata. Useful for standardizing 
    message representation across different communication platforms.
    
    Attributes:
        platform: The communication platform (e.g., 'imessage', 'sms').
        sender_id: Unique identifier for the message sender.
        text: The actual message content.
        timestamp: Precise time the message was sent in ISO 8601 format.
        metadata: Additional platform-specific information.
    """
    platform: str = Field(..., description="The platform from which the message originates (e.g., 'imessage').")
    sender_id: str = Field(..., description="The sender's identifier, such as a phone number or unique ID.")
    text: str = Field(..., description="The raw text content of the incoming message.")
    timestamp: str = Field(..., description="ISO 8601 formatted timestamp of when the message was sent.")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional platform-specific metadata, e.g., chat IDs.")

    class Config:
        json_schema_extra = {
            "example": {
                "platform": "imessage",
                "sender_id": "+15555555555",
                "text": "Don’t forget your meds",
                "timestamp": "2025-04-09T04:00:00Z",
                "metadata": {
                    "chat_id": "BBUUID-ABC123"
                }
            }
        }


class ProxyRequest(BaseModel):
    """
    Represents a proxy request with message, user identification, context, and optional mode and memories.
    
    Attributes:
        message (IncomingMessage): The incoming message associated with the proxy request.
        user_id (str): The unique identifier of the user making the request.
        context (str): The context of the proxy request.
        mode (Optional[str], optional): An optional mode specification for the request. Defaults to None.
        memories (Optional[List[str]], optional): An optional list of memory references. Defaults to None.
    """
    message: IncomingMessage
    user_id: str
    context: str
    mode: Optional[str] = None
    memories: Optional[List[str]] = None


# reworked models go down here


class ProxyOneShotRequest(BaseModel):
    """
    Represents a request for a one-shot proxy interaction with a language model.
    
    Attributes:
        model (str): The name of the model to be used for generating the response. Defaults to 'nemo'.
        prompt (str): The input text or prompt to be processed by the model.
        temperature (float): Controls the randomness of the model's output. Defaults to 0.7.
        max_tokens (int): The maximum number of tokens to generate in the response. Defaults to 256.
    """
    model: Optional[str]            = Field('nemo', description="The model to be used for generating the response.")
    prompt: str                     = Field(..., description="The prompt or input text for the model.")
    temperature: Optional[float]    = Field(0.7, description="The temperature setting for randomness in the model's output.")
    max_tokens: Optional[int]       = Field(256, description="The maximum number of tokens to generate in the response.")

    class Config:
        json_schema_extra = {
            "example": {
                "model": "nemo",
                "prompt": "Don't forget your meds",
                "temperature": 0.7,
                "max_tokens": 256
            }
        }


class ProxyMessage(BaseModel):
    """
    Represents a message in a proxy conversation with a defined role and content.
    
    Attributes:
        role (str): The role of the message sender, such as 'user' or 'assistant'.
        content (str): The textual content of the message.
    """
    role: Literal["user", "assistant", "system"]  = Field(..., description="The role of the message sender (e.g., 'user', 'assistant').")
    content: str                        = Field(..., description="The content of the message.")


class ProxyMultiTurnRequest(BaseModel):
    """
    Represents a request for a multi-turn proxy interaction with a language model.
    
    Attributes:
        model (str): The name of the model to be used for generating the response. Defaults to 'nemo'.
        messages (List[ProxyMessage]): A list of messages representing the conversation history.
        temperature (float): Controls the randomness of the model's output. Defaults to 0.7.
        max_tokens (int): The maximum number of tokens to generate in the response. Defaults to 256.
    """
    model: Optional[str]                = Field('nemo', description="The model to be used for generating the response.")
    messages: List[ProxyMessage]        = Field(..., description="List of messages for multi-turn conversation.")
    temperature: Optional[float]        = Field(0.7, description="The temperature setting for randomness in the model's output.")
    max_tokens: Optional[int]           = Field(256, description="The maximum number of tokens to generate in the response.")

    class Config:
        json_schema_extra = {
            "example": {
                "model": "nemo",
                "messages": [
                    {
                        "role": "user",
                        "content": "Don't forget your meds"
                    },
                    {
                        "role": "assistant",
                        "content": "Sure, I will remind you!"
                    }
                ],
                "temperature": 0.7,
                "max_tokens": 256
            }
        }


class ProxyResponse(BaseModel):
    """
    Represents the response from a proxy model interaction.
    
    Attributes:
        response (str): The text response generated by the model.
        generated_tokens (int): The number of tokens consumed in generating the response.
        timestamp (str): The ISO 8601 formatted timestamp of when the response was generated.
    """
    response: str                   = Field(..., description="The generated text response from the model.")
    generated_tokens: int           = Field(..., description="The number of tokens used in the response.")
    timestamp: str                  = Field(..., description="ISO 8601 formatted timestamp of when the response was generated.")

    class Config:
        json_schema_extra = {
            "example": {
                "response": "Don't forget your meds",
                "generated_tokens": 10,
                "timestamp": "2025-04-09T04:00:00Z"
            }
        }

