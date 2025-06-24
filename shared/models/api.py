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
    model: str     # actual model name
    options: Optional[Dict[str, Any]] = None  # provider-specific options (includes temperature, max_tokens, etc.)
    content: Optional[str] = None  # for single-turn (was 'prompt')
    messages: Optional[List[Any]] = None  # for multi-turn (list of messages as dicts)
    n: Optional[int] = 1
    platform: Optional[str] = "api"  # Add platform field with default 'api'
    # Add other fields as needed for compatibility

class ChatCompletionRequest(BaseModel):
    """
    Represents a provider-agnostic chat completion request.
    """
    model: str                          = Field(_default_mode["model"], description="The model to be used, e.g. 'nemo'.")
    messages: List[Dict[str, str]]         = Field(..., description="A list of messages representing the conversation history.")
    options: Optional[Dict[str, Any]]        = Field(None, description="Provider-specific options (temperature, max_tokens, etc.)")

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
    message: Dict[str, str]                = Field(..., description="Generated message.")
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
