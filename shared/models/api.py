"""
This module defines Pydantic models for API requests and responses related to language model completions and chat interactions.
Classes:
    CompletionRequest: Represents a request for a model completion, including model selection, options, content, and platform.
    ChatCompletionRequest: Represents a request for a chat completion, including conversation history and provider options.
    ChatCompletionChoice: Represents an individual choice in a chat completion response, including the generated message and finish reason.
    ChatUsage: Represents token usage statistics for a chat completion.
    ChatCompletionResponse: Represents a complete chat completion response, including choices and usage statistics.
Configuration:
    Loads default model configuration from a JSON config file specified by the KIRISHIMA_CONFIG environment variable or a default path.
Intended Usage:
    These models are intended for use in API endpoints that handle language model completions and chat-based interactions, providing OpenAI-compatible request and response formats.
"""
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from pydantic import BaseModel, Field
import json
import os

# Load config and get default mode values for defaults
CONFIG_PATH = os.environ.get("KIRISHIMA_CONFIG", "/app/config/config.json")
with open(CONFIG_PATH) as f:
    _config = json.load(f)
_default_mode = _config["llm"]["mode"]["default"]

class CompletionRequest(BaseModel):
    """
    Represents a request for a model completion.

    Attributes:
        model (str): The model to be used, e.g. 'nemo'.
        options (Optional[Dict[str, Any]]): Provider-specific options such as temperature, max_tokens, etc.
        content (Optional[str]): The content to be processed by the model.
        n (Optional[int]): Number of completions to generate. Defaults to 1.
        messages (Optional[List[Any]]): List of messages for multi-turn conversations.
        platform (Optional[str]): Platform for which the request is intended (e.g., 'api'). Defaults to 'api'.
    """
    model: str                          = Field(_default_mode["model"], description="The model to be used, e.g. 'nemo'.")
    options: Optional[Dict[str, Any]]   = Field(None, description="Provider-specific options (temperature, max_tokens, etc.)")
    content: Optional[str]              = Field(None, description="The content to be processed by the model.")
    n: Optional[int]                    = Field(1, description="Number of completions to generate.")
    messages: Optional[List[Any]]       = Field(None, description="List of messages for multi-turn conversations.")
    platform: Optional[str]             = Field("api", description="Platform for which the request is intended (e.g., 'api').")

class ChatCompletionRequest(BaseModel):
    """
    Represents a request for a chat completion.

    Attributes:
        model (str): The model to be used, e.g. 'nemo'.
        messages (List[Dict[str, str]]): A list of messages representing the conversation history.
        options (Optional[Dict[str, Any]]): Provider-specific options (temperature, max_tokens, etc.).

    Example:
        {
            "model": "default",
            "messages": [
                {"role": "user", "content": "What's the weather like today?"},
                {"role": "assistant", "content": "It's sunny and warm."}
            ],
            "options": {"temperature": 0.7, "max_tokens": 256}
        }
    """
    model: str                          = Field(_default_mode["model"], description="The model to be used, e.g. 'nemo'.")
    messages: List[Dict[str, str]]      = Field(..., description="A list of messages representing the conversation history.")
    options: Optional[Dict[str, Any]]   = Field(None, description="Provider-specific options (temperature, max_tokens, etc.)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "model": "default",
                "messages": [
                    {"role": "user", "content": "What's the weather like today?"},
                    {"role": "assistant", "content": "It's sunny and warm."}
                ],
                "options": {"temperature": 0.7, "max_tokens": 256}
            }
        },
        "extra": "allow"
    }


class ChatCompletionChoice(BaseModel):
    """
    Represents an individual choice in the OpenAI chat completion response.
    
    Attributes:
        index (int): The index of the choice.
        message (Dict[str, str]): The generated message.
        finish_reason (Optional[str]): The reason for finishing the completion.
    """
    index: int                          = Field(..., description="Index of the completion choice.")
    message: Dict[str, str]             = Field(..., description="Generated message.")
    finish_reason: Optional[str]        = Field("stop", description="Reason for finishing the completion.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "The weather is sunny and warm."
                },
                "finish_reason": "stop"
            }
        }
    }


class ChatUsage(BaseModel):
    """
    Represents token usage information.
    
    Attributes:
        prompt_tokens (int): Number of tokens in the prompt.
        completion_tokens (int): Number of tokens generated.
        total_tokens (int): Total tokens used.
    """
    prompt_tokens: int                  = Field(..., description="Tokens in the prompt.")
    completion_tokens: int              = Field(..., description="Tokens in the completion.")
    total_tokens: int                   = Field(..., description="Total tokens used.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }
    }


class ChatCompletionResponse(BaseModel):
    """
    Represents an OpenAI-compatible chat completion response.
    
    Attributes:
        id (str): A unique identifier for the response.
        object (str): The object type, typically "chat.completion".
        created (int): UNIX timestamp of creation.
        model (str): The model used.
        choices (List[ChatCompletionChoice]): A list of response choices.
        usage (ChatUsage): Token usage statistics.
    """
    id: str                             = Field(..., description="Unique response ID.")
    object: str                         = Field("chat.completion", description="Response type.")
    created: int                        = Field(..., description="Creation timestamp (UNIX epoch).")
    model: str                          = Field(..., description="The model used.")
    choices: List[ChatCompletionChoice] = Field(..., description="List of completion choices.")
    usage: ChatUsage                    = Field(..., description="Token usage details.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "chatcmpl-1234567890",
                "object": "chat.completion",
                "created": 1696147200,
                "model": "nemo",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "The weather is sunny and warm."
                        },
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30
                }
            }
        }
    }
