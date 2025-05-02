"""
This module defines a set of Pydantic models for handling structured data in a proxy system. 
The models are designed to standardize and validate incoming and outgoing data for various 
interactions, including single-turn and multi-turn conversations, as well as specific 
platform integrations like Discord.
Classes:
    IncomingMessage:
    ProxyRequest:
        Represents a proxy request with message, user identification, context, and optional 
        mode and memories.
    ProxyOneShotRequest:
    ChatMessage:
    ChatMessages:
    ProxyMultiTurnRequest:
    ProxyResponse:
    ProxyDiscordDMRequest:
    OllamaResponse:
Each model includes detailed attributes, validation rules, and example configurations 
to facilitate consistent usage and integration across different components of the system.
"""

from shared.config import LLM_DEFAULTS


from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from shared.models.memory import MemoryEntryFull
from shared.models.contacts import Contact
from shared.models.discord import DiscordDirectMessage


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
    platform: str               = Field(..., description="The platform from which the message originates (e.g., 'imessage').")
    sender_id: str              = Field(..., description="The sender's identifier, such as a phone number or unique ID.")
    text: str                   = Field(..., description="The raw text content of the incoming message.")
    timestamp: str              = Field(..., description="ISO 8601 formatted timestamp of when the message was sent.")
    metadata: Dict[str, Any]    = Field(default_factory=dict, description="Additional platform-specific metadata, e.g., chat IDs.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "platform": "imessage",
                "sender_id": "+15555555555",
                "text": "Don't forget your meds",
                "timestamp": "2025-04-09T04:00:00Z",
                "metadata": {
                    "chat_id": "BBUUID-ABC123"
                }
            }
        }
    }


class ProxyRequest(BaseModel):
    """
    Represents a proxy request with message, user identification, context, and optional mode and memories.
    
    Attributes:
        message (IncomingMessage): The incoming message associated with the proxy request.
        user_id (str): The uuid of the user making the request.
        context (str): The context of the proxy request.
        mode (Optional[str], optional): An optional mode specification for the request. Defaults to None.
        memories (Optional[List[MemoryEntryFull]], optional): A list of memory entries associated with the request. Defaults to None.
        summaries (Optional[str], optional): A list of user summaries associated with the request. Defaults to None.
    """
    message: IncomingMessage                        = Field(..., description="The incoming message associated with the proxy request.")
    user_id: str                                    = Field(..., description="The uuid of the user making the request.")
    context: str                                    = Field(..., description="The context of the proxy request.")
    mode: Optional[str]                             = Field(None, description="An optional mode specification for the request.")
    memories: Optional[List[MemoryEntryFull]]       = Field(None, description="An optional list of memory references.")
    summaries: Optional[str]                        = Field(None, description="An optional list of user summaries.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": {
                    "platform": "imessage",
                    "sender_id": "+15555555555",
                    "text": "Don't forget your meds",
                    "timestamp": "2025-04-09T04:00:00Z",
                    "metadata": {
                        "chat_id": "BBUUID-ABC123"
                    }
                },
                "user_id": "1234567890",
                "context": "Reminder to take meds",
                "mode": None,
                "memories": [
                    {
                        "memory": "Reminder to take meds",
                        "component": "proxy",
                        "priority": 1.0,
                        "mode": None
                    }
                ],
                "summaries": None
            }
        }
    }


class ProxyOneShotRequest(BaseModel):
    """
    Represents a request for a one-shot proxy interaction with a language model.
    
    Attributes:
        model (str): The name of the model to be used for generating the response. Defaults to 'nemo'.
        prompt (str): The input text or prompt to be processed by the model.
        temperature (float): Controls the randomness of the model's output. Defaults to 0.7.
        max_tokens (int): The maximum number of tokens to generate in the response. Defaults to 256.
    """
    model: Optional[str]            = Field(LLM_DEFAULTS['model'], description="The model to be used for generating the response.")
    prompt: str                     = Field(..., description="The prompt or input text for the model.")
    temperature: Optional[float]    = Field(LLM_DEFAULTS['temperature'], description="The temperature setting for randomness in the model's output.")
    max_tokens: Optional[int]       = Field(LLM_DEFAULTS['max_tokens'], description="The maximum number of tokens to generate in the response.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "model": "nemo",
                "prompt": "Don't forget your meds",
                "temperature": 0.7,
                "max_tokens": 256
            }
        }
    }


class ChatMessage(BaseModel):
    """
    Represents a message in a proxy conversation with a defined role and content.
    
    Attributes:
        role (str): The role of the message sender, such as 'user' or 'assistant'.
        content (str): The textual content of the message.
    """
    role: Literal["user", "assistant", "system"]    = Field(..., description="The role of the message sender (e.g., 'user', 'assistant').")
    content: str                                    = Field(..., description="The content of the message.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "role": "user",
                "content": "Don't forget your meds"
            }
        }
    }


class ChatMessages(BaseModel):
    """
    Represents a collection of chat messages for a multi-turn conversation.
    
    Attributes:
        messages (List[ChatMessage]): A list of chat messages representing the conversation history.
    """
    messages: List[ChatMessage]                     = Field(..., description="List of messages for multi-turn conversation.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "messages": [
                    {
                        "role": "user",
                        "content": "Don't forget your meds"
                    },
                    {
                        "role": "assistant",
                        "content": "Sure, I will remind you!"
                    }
                ]
            }
        }
    }


class ProxyMultiTurnRequest(BaseModel):
    """
    Represents a request for a multi-turn proxy interaction with a language model.
    
    Attributes:
        model (str): The name of the model to be used for generating the response. Defaults to 'nemo'.
        messages (List[ChatMessage]): A list of messages representing the conversation history.
        temperature (float): Controls the randomness of the model's output. Defaults to 0.7.
        max_tokens (int): The maximum number of tokens to generate in the response. Defaults to 256.
        memories (Optional[List[MemoryEntryFull]]): A list of memory entries associated with the conversation.
        summaries (Optional[str]): A list of user summaries associated with the conversation.
        mode (Optional[str]): An optional mode specification for the request.
        platform (Optional[str]): The platform from which the request originates.
        username (Optional[str]): The username of the person making the request.
    """
    model: Optional[str]                        = Field(LLM_DEFAULTS['model'], description="The model to be used for generating the response.")
    messages: List[ChatMessage]                 = Field(..., description="List of messages for multi-turn conversation.")
    temperature: Optional[float]                = Field(LLM_DEFAULTS['temperature'], description="The temperature setting for randomness in the model's output.")
    max_tokens: Optional[int]                   = Field(LLM_DEFAULTS['max_tokens'], description="The maximum number of tokens to generate in the response.")
    memories: Optional[List[MemoryEntryFull]]   = Field(None, description="List of memory entries associated with the conversation.")
    summaries: Optional[str]                    = Field(None, description="List of user summaries associated with the conversation.")
    mode: Optional[str]                         = Field(None, description="An optional mode specification for the request.")
    platform: Optional[str]                     = Field(None, description="The platform from which the request originates.")
    username: Optional[str]                     = Field(None, description="The username of the person making the request.")

    model_config = {
        "json_schema_extra": {
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
                "max_tokens": 256,
                "memories": [
                    {
                        "memory": "Reminder to take meds",
                        "component": "proxy",
                        "priority": 1.0,
                        "mode": "default"
                    }
                ],
                "summaries": None
            }
        }
    }


class ProxyResponse(BaseModel):
    """
    Represents the response from a proxy model interaction.
    
    Attributes:
        response (str): The text response generated by the model.
        timestamp (str): The ISO 8601 formatted timestamp of when the response was generated.
        eval_count (int): The number of tokens used in the response.
        prompt_eval_count (int): The number of tokens used in the prompt.
    """
    response: str                       = Field(..., description="The generated text response from the model.")
    timestamp: str                      = Field(..., description="ISO 8601 formatted timestamp of when the response was generated.")
    eval_count: int                     = Field(None, description="The number of tokens used in the response.")
    prompt_eval_count: int              = Field(None, description="The number of tokens used in the prompt.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "response": "Don't forget your meds",
                "timestamp": "2025-04-09T04:00:00Z",
                "eval_count": 10,
                "prompt_eval_count": 5
            }
        }
    }


class ProxyDiscordDMRequest(BaseModel):
    """
    Represents a proxy request for a Discord direct message interaction.
    
    This model encapsulates the details of a Discord direct message request,
    including the original message, conversation history, user contact information,
    and optional metadata such as admin status, conversation mode, memories, and summaries.
    
    Attributes:
        message (DiscordDirectMessage): The incoming Discord direct message.
        messages (List[ChatMessage]): Conversation history for multi-turn interactions.
        contact (Contact): User contact information.
        is_admin (Optional[bool]): Indicates if the user is an admin (defaults to False).
        mode (Optional[str]): Specifies the interaction mode (defaults to 'guest').
        memories (Optional[List[MemoryEntryFull]]): Optional contextual memory references.
        summaries (Optional[str]): Optional summary of the conversation.
    """
    message: DiscordDirectMessage               = Field(..., description="The incoming message associated with the proxy request.")
    messages: List[ChatMessage]                 = Field(..., description="List of messages for multi-turn conversation.")
    contact: Contact                            = Field(..., description="The contact information associated with the user.")
    is_admin: Optional[bool]                    = Field(False, description="Indicates if the user is an admin.")
    mode: Optional[str]                         = Field("guest", description="An optional mode specification for the request.")
    memories: Optional[List[MemoryEntryFull]]   = Field(None, description="An optional list of memory references.")
    summaries: Optional[str]                    = Field(None, description="An optional list of user summaries.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": {
                    "platform": "discord",
                    "sender_id": "1234567890",
                    "text": "Don't forget your meds",
                    "timestamp": "2025-04-09T04:00:00Z",
                    "metadata": {
                        "chat_id": "BBUUID-ABC123"
                    }
                },
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
                "contact": {
                    "id": 1,
                    "aliases": ["John Doe", "+15555555555"],
                    "fields": [
                        {"key": "email", "value": "john@doe.com"},
                        {"key": "phone", "value": "+1234567890"}
                    ],
                    "notes": "Preferred contact during business hours."
                },
                "is_admin": False,
                "mode": "guest",
                "memories": [
                    {
                        "memory": "Reminder to take meds",
                        "component": "proxy",
                        "priority": 1.0,
                        "mode": "default"
                    }
                ],
                "summaries": None
            }
        }
    }


class OllamaRequest(BaseModel):
    """
    Represents a request to the Ollama API for generating text responses.
    
    Attributes:
        model Optional[str]: The name of the model to be used for generating the response.
        prompt (str): The input text or prompt to be processed by the model.
        temperature (Optional[float]): Controls the randomness of the model's output.
        max_tokens (Optional[int]): The maximum number of tokens to generate in the response.
        stream (Optional[bool]): Indicates whether to stream the response.
        raw (Optional[bool]): Indicates whether to return the raw response.
    """
    model: Optional[str]                = Field(LLM_DEFAULTS['model'], description="The name of the model to be used for generating the response.")
    prompt: str                         = Field(..., description="The input text or prompt to be processed by the model.")
    temperature: Optional[float]        = Field(LLM_DEFAULTS['temperature'], description="Controls the randomness of the model's output.")
    max_tokens: Optional[int]           = Field(LLM_DEFAULTS['max_tokens'], description="The maximum number of tokens to generate in the response.")
    stream: Optional[bool]              = Field(False, description="Indicates whether to stream the response.")
    raw: Optional[bool]                 = Field(True, description="Indicates whether to return the raw response.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "model": "nemo",
                "prompt": "Don't forget your meds",
                "temperature": 0.7,
                "max_tokens": 256,
                "stream": False,
                "raw": True
            }
        }
    }


class OllamaResponse(BaseModel):
    """
    Represents the response from the Ollama API.
    
    Attributes:
        model (str): The name of the model used for generating the response.
        created_at (str): The timestamp when the response was created.
        response (str): The generated text response from the model.
        done (bool): Indicates whether the response generation is complete.
        done_reason (str): The reason for completion of the response generation.
        total_duration (int): Total duration of the request in nanoseconds.
        load_duration (int): Duration of loading the model in nanoseconds.
        prompt_eval_count (int): Number of times the prompt was evaluated.
        prompt_eval_duration (int): Duration of prompt evaluation in nanoseconds.
        eval_count (int): Number of evaluations performed by the model.
        eval_duration (int): Duration of evaluations in nanoseconds.
    """
    model: str                          = Field(..., description="The name of the model used for generating the response.")
    created_at: str                     = Field(..., description="The timestamp when the response was created.")
    response: str                       = Field(..., description="The generated text response from the model.")
    done: bool                          = Field(..., description="Indicates whether the response generation is complete.")
    done_reason: str                    = Field(..., description="The reason for completion of the response generation.")
    total_duration: int                 = Field(..., description="Total duration of the request in nanoseconds.")
    load_duration: int                  = Field(..., description="Duration of loading the model in nanoseconds.")
    prompt_eval_count: int              = Field(..., description="Number of times the prompt was evaluated.")
    prompt_eval_duration: int           = Field(..., description="Duration of prompt evaluation in nanoseconds.")
    eval_count: int                     = Field(..., description="Number of evaluations performed by the model.")
    eval_duration: int                  = Field(..., description="Duration of evaluations in nanoseconds.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "model": "nemo",
                "created_at": "2025-04-09T04:00:00Z",
                "response": "Don't forget your meds",
                "done": True,
                "done_reason": "completed",
                "total_duration": 1000000,
                "load_duration": 500000,
                "prompt_eval_count": 1,
                "prompt_eval_duration": 200000,
                "eval_count": 1,
                "eval_duration": 300000
            }
        }
    }