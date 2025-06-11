"""
This module defines Pydantic models for proxying and standardizing requests and responses
across various language model providers and communication platforms.
Models:
    - IncomingMessage: Standardizes incoming messages from different platforms.
    - ProxyRequest: Represents a proxy request with message, user, context, and optional memory/contextual data.
    - ProxyOneShotRequest: Represents a one-shot proxy interaction with a language model.
    - MultiTurnRequest: Represents a multi-turn conversation request with a language model.
    - ProxyResponse: Standardizes the response from a proxy model interaction.
    - ProxyDiscordDMRequest: Encapsulates a Discord direct message proxy request with conversation and user details.
    - OllamaRequest: Represents a request to the Ollama API for text generation.
    - OpenAIRequest: Represents a request to the OpenAI API for text generation.
    - RespondJsonRequest: Represents a JSON request for generating a model response.
    - DivoomRequest: Represents a request for the Divoom API (structure only).
    - OllamaResponse: Standardizes the response from the Ollama API.
    - OpenAIResponse: Standardizes and parses the response from the OpenAI API.
These models facilitate structured, type-safe interactions between application logic,
language model APIs, and various communication platforms, supporting both single-turn
and multi-turn conversational flows, as well as provider-specific options and metadata.
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


class MultiTurnRequest(BaseModel):
    """
    Represents a request for a multi-turn proxy interaction with a language model.
    Attributes:
        model (str): The name of the model to be used for generating the response.
        provider (Optional[str]): The provider for the model (e.g., 'openai', 'ollama').
        messages (List[Dict[str, Any]]): A list of messages representing the conversation history.
        options (Optional[Dict[str, Any]]): Provider-specific options (temperature, max_tokens, etc.).
        memories (Optional[List[MemoryEntryFull]]): A list of memory entries associated with the conversation.
        summaries (Optional[str]): A list of user summaries associated with the conversation.
        platform (Optional[str]): The platform from which the request originates.
        username (Optional[str]): The username of the person making the request.
        tools (Optional[List[Dict[str, Any]]]): A list of tools available for the model to call.
        user_id (Optional[int]): The user ID associated with the request.
    """
    model: str                                 = Field(..., description="The model to be used for generating the response.")
    provider: Optional[str]                    = Field(None, description="The provider for the model (e.g., 'openai', 'ollama').")
    messages: List[Dict[str, Any]]             = Field(..., description="List of messages for multi-turn conversation.")
    options: Optional[Dict[str, Any]]          = Field(None, description="Provider-specific options (temperature, max_tokens, etc.)")
    memories: Optional[List[MemoryEntryFull]]  = Field(None, description="List of memory entries associated with the conversation.")
    summaries: Optional[str]                   = Field(None, description="List of user summaries associated with the conversation.")
    platform: Optional[str]                    = Field(None, description="The platform from which the request originates.")
    username: Optional[str]                    = Field(None, description="The username of the person making the request.")
    tools: Optional[List[Dict[str, Any]]]      = Field(None, description="List of tools available for the model to call.")
    user_id: Optional[str]                     = Field(None, description="The user ID associated with the request.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "model": "gpt-4.1",
                "provider": "openai",
                "messages": [
                    {"role": "user", "content": "Don't forget your meds"},
                    {"role": "assistant", "content": "Sure, I will remind you!"}
                ],
                "options": {"temperature": 0.7, "max_tokens": 256},
                "memories": None,
                "summaries": None,
                "platform": "api",
                "username": "randi",
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "remind_user",
                            "description": "Reminds the user to take their medication.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "medication_name": {
                                        "type": "string",
                                        "description": "The name of the medication to remind about."
                                    }
                                },
                                "required": ["medication_name"]
                            }
                        }
                    }
                ],
                "user_id": "1234567890"
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
        tool_calls (Optional[list]): List of tool calls returned by the model, if any.
        function_call (Optional[dict]): Function call object returned by the model, if any.
    """
    response: str                       = Field(..., description="The generated text response from the model.")
    timestamp: str                      = Field(..., description="ISO 8601 formatted timestamp of when the response was generated.")
    eval_count: int                     = Field(None, description="The number of tokens used in the response.")
    prompt_eval_count: int              = Field(None, description="The number of tokens used in the prompt.")
    tool_calls: Optional[list]          = Field(None, description="List of tool calls returned by the model, if any.")
    function_call: Optional[dict]       = Field(None, description="Function call object returned by the model, if any.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "response": "Don't forget your meds",
                "timestamp": "2025-04-09T04:00:00Z",
                "eval_count": 10,
                "prompt_eval_count": 5,
                "tool_calls": [
                    {
                        "type": "function",
                        "function": {
                            "name": "remind_user",
                            "description": "Reminds the user to take their medication.",
                            "parameters": {
                                "medication_name": "Aspirin"
                            }
                        }
                    }
                ],
                "function_call": None
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
        messages (List[Dict[str, str]]): Conversation history for multi-turn interactions.
        contact (Contact): User contact information.
        is_admin (Optional[bool]): Indicates if the user is an admin (defaults to False).
        mode (Optional[str]): Specifies the interaction mode (defaults to 'guest').
        memories (Optional[List[MemoryEntryFull]]): Optional contextual memory references.
        summaries (Optional[str]): Optional summary of the conversation.
    """
    message: DiscordDirectMessage               = Field(..., description="The incoming message associated with the proxy request.")
    messages: List[Dict[str, str]]              = Field(..., description="List of messages for multi-turn conversation.")
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
        model (str): The name of the model to be used for generating the response.
        prompt (str): The input text or prompt to be processed by the model.
        options (Optional[Dict[str, Any]]): Provider-specific options (temperature, max_tokens, etc.).
        stream (Optional[bool]): Indicates whether to stream the response.
        raw (Optional[bool]): Indicates whether to return the raw response.
        format (Optional[object]): The class of the response, typically a Pydantic model.
    """
    model: str                                 = Field(..., description="The name of the model to be used for generating the response.")
    prompt: str                                = Field(..., description="The input text or prompt to be processed by the model.")
    options: Optional[Dict[str, Any]]          = Field(None, description="Provider-specific options (temperature, max_tokens, etc.)")
    stream: Optional[bool]                     = Field(False, description="Indicates whether to stream the response.")
    raw: Optional[bool]                        = Field(True, description="Indicates whether to return the raw response.")
    format: Optional[object]                   = Field(None, description="The class of the response, typically a Pydantic model.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "model": "nemo",
                "prompt": "Don't forget your meds",
                "options": {"temperature": 0.7, "max_tokens": 256},
                "stream": False,
                "raw": True,
                "format": "ProxyDiscordDMRequest"
            }
        }
    }


class OpenAIRequest(BaseModel):
    """
    Represents a request to the OpenAI API for generating text responses.
    
    Attributes:
        model (str): The name of the model to be used for generating the response.
        messages (List[Dict[str, str]]): List of messages for multi-turn conversation.
        options (Optional[Dict[str, Any]]): Provider-specific options (temperature, max_tokens, etc.).
        stream (Optional[bool]): Indicates whether to stream the response.
    """
    model: str                                      = Field(..., description="The name of the model to be used for generating the response.")
    messages: List[Dict[str, Any]]                  = Field(..., description="List of messages for multi-turn conversation.")
    options: Optional[Dict[str, Any]]               = Field(None, description="Provider-specific options (temperature, max_tokens, etc.)")
    stream: Optional[bool]                          = Field(False, description="Indicates whether to stream the response.")
    tools: Optional[List[Dict[str, Any]]]           = Field(None, description="List of tools available for the model to call.")
    tool_choice: Optional[Literal["auto", "none"]]  = Field("auto", description="How to handle tool calls: 'auto' to allow, 'none' to disable.")
    model_config = {
        "json_schema_extra": {
            "example": {
                "model": "gpt-4.1",
                "messages": [
                    {"role": "user", "content": "Don't forget your meds"},
                    {"role": "assistant", "content": "Sure, I will remind you!"}
                ],
                "options": {"temperature": 0.7, "max_tokens": 256},
                "stream": False,
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "remind_user",
                            "description": "Reminds the user to take their medication.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "medication_name": {
                                        "type": "string",
                                        "description": "The name of the medication to remind about."
                                    }
                                },
                                "required": ["medication_name"]
                            }
                        }
                    }
                ],
                "tool_choice": "auto"
            }
        }
    }


class RespondJsonRequest(BaseModel):
    """
    A Pydantic model representing a JSON request for generating a model response.
    
    Attributes:
        model (str): The name of the model to be used for generating the response.
        prompt (str): The input text or prompt to be processed by the model.
        temperature (float): Controls the randomness of the model's output. Higher values increase creativity.
        max_tokens (int): The maximum number of tokens to generate in the response.
        format (object): The class of the response, typically a Pydantic model.
    """
    model: str                          = Field(..., description="The model to be used for generating the response.")
    prompt: str                         = Field(..., description="The prompt or input text for the model.")
    temperature: float                  = Field(..., description="The temperature setting for randomness in the model's output.")
    max_tokens: int                     = Field(..., description="The maximum number of tokens to generate in the response.")
    format: object                      = Field(None, description="the class of the response, typically a Pydantic model.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "model": "nemo:latest",
                "prompt": "Don't forget your meds",
                "temperature": 0.7,
                "max_tokens": 256,
                "format": OllamaRequest
            }
        }
    }

class DivoomRequest(BaseModel):
    model: str
    temperature: float
    max_tokens: int
    messages: List[Dict[str, str]]

class OllamaResponse(BaseModel):
    """
    Represents a response from the Ollama API.
    """
    response: str                           = Field(..., description="The generated text response from the model.")
    eval_count: Optional[int]               = Field(None, description="The number of tokens used in the response.")
    prompt_eval_count: Optional[int]        = Field(None, description="The number of tokens used in the prompt.")
    # Add any other fields as needed from Ollama's API

    model_config = {
        "json_schema_extra": {
            "example": {
                "response": "Don't forget your meds",
                "eval_count": 10,
                "prompt_eval_count": 5
            }
        }
    }


class OpenAIResponse(BaseModel):
    """
    Represents a response from the OpenAI API, parsing and extracting key details from the API response.
    
    Attributes:
        response (str): The generated text response from the model.
        eval_count (Optional[int]): The number of tokens used in generating the response.
        prompt_eval_count (Optional[int]): The number of tokens used in the input prompt.
        tool_calls (Optional[list]): List of tool calls returned by the model, if any.
        function_call (Optional[dict]): Function call object returned by the model, if any.
    
    The `from_api` class method provides a convenient way to transform a raw OpenAI API 
    response into a structured OpenAIResponse object, handling extraction of response 
    content, token usage, and optional tool/function call information.
    """
    response: str                       = Field(..., description="The generated text response from the model.")
    eval_count: Optional[int]           = Field(None, description="The number of tokens used in the response.")
    prompt_eval_count: Optional[int]    = Field(None, description="The number of tokens used in the prompt.")
    tool_calls: Optional[list]          = Field(None, description="List of tool calls returned by the model, if any.")
    function_call: Optional[dict]       = Field(None, description="Function call object returned by the model, if any.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "response": None,
                "eval_count": 10,
                "prompt_eval_count": 5,
                "tool_calls": [
                    {
                        "id": "call_abc123",
                        "type": "function",
                        "function": {
                            "name": "update_divoom",
                            "arguments": "{\"emoji\": \"😀\"}"
                        }
                    }
                ],
                "function_call": None
            }
        }
    }

    @classmethod
    def from_api(cls, api_response: dict) -> "OpenAIResponse":
        # Parse OpenAI API response (chat/completions)
        choices = api_response.get("choices", [])
        message = choices[0]["message"] if choices else {}
        content = message.get("content", "")
        tool_calls = message.get("tool_calls")
        function_call = message.get("function_call")
        usage = api_response.get("usage", {})
        return cls(
            response=content.strip() if content else "",
            eval_count=usage.get("completion_tokens"),
            prompt_eval_count=usage.get("prompt_tokens"),
            tool_calls=tool_calls,
            function_call=function_call
        )