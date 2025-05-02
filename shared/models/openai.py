"""
This module defines Pydantic models for OpenAI-compatible completion and chat APIs.
Classes:
    OpenAICompletionRequest: Represents a request for OpenAI-style text completions.
    OpenAICompletionChoice: Represents an individual completion choice in the response.
    OpenAIUsage: Contains token usage statistics for completions.
    OpenAICompletionResponse: Represents the response for an OpenAI-style completion request.
    ChatCompletionRequest: Represents a request for OpenAI-compatible chat completions.
    ChatCompletionChoice: Represents an individual choice in the chat completion response.
    ChatUsage: Contains token usage statistics for chat completions.
    ChatCompletionResponse: Represents the response for an OpenAI-compatible chat completion request.
Each class is designed to closely match the structure of OpenAI's API, enabling compatibility with clients expecting OpenAI-style request and response formats.
"""

from typing import List, Optional
from pydantic import BaseModel, Field
from shared.models.proxy import ChatMessage
from shared.config import LLM_DEFAULTS
class OpenAICompletionRequest(BaseModel):
    """
    OpenAI-style completions request.

    Attributes:
        prompt (str): The prompt to generate completions for.
        model (Optional[str]): The model to use (default: "nemo").
        temperature (Optional[float]): The sampling temperature (default: 0.7).
        max_tokens (Optional[int]): Maximum tokens to generate (default: 256).
        n (Optional[int]): Number of completions to generate (default: 1).
    """
    prompt: str                         = Field(..., description="The prompt to generate completions for.")
    model: Optional[str]                = Field(LLM_DEFAULTS['model'], description="The model to be used.")
    temperature: Optional[float]        = Field(LLM_DEFAULTS['temperature'], description="Sampling temperature.")
    max_tokens: Optional[int]           = Field(LLM_DEFAULTS['max_tokens'], description="Maximum tokens to generate.")
    n: Optional[int]                    = Field(default=1, description="Number of completions to generate.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "prompt": "What is the weather like today?",
                "model": "nemo",
                "temperature": 0.7,
                "max_tokens": 256,
                "n": 1
            }
        },
        "extra": "allow"
    }


class OpenAICompletionChoice(BaseModel):
    """
    Represents an individual completion choice in the OpenAI-style response.
    
    Attributes:
        text (str): The generated response text.
        index (int): The index of the completion.
        logprobs (Optional[dict]): Log probabilities (if available).
        finish_reason (Optional[str]): The reason the completion finished.
    """
    text: str                           = Field(..., description="Generated response text.")
    index: int                          = Field(..., description="Index of the completion choice.")
    logprobs: Optional[dict]            = Field(None, description="Log probabilities (if available).")
    # Note: logprobs is not used in the current implementation, but included for completeness.
    finish_reason: Optional[str]        = Field("stop", description="Reason for finishing the completion.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "text": "The weather is sunny and warm.",
                "index": 0,
                "logprobs": None,
                "finish_reason": "stop"
            }
        }
    }


class OpenAIUsage(BaseModel):
    """
    Represents usage statistics in the OpenAI-style response.
    
    Attributes:
        prompt_tokens (int): Number of tokens in the prompt.
        completion_tokens (int): Number of tokens generated as completion.
        total_tokens (int): Total tokens counted (prompt + completion).
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


class OpenAICompletionResponse(BaseModel):
    """
    OpenAI-style completions response.
    
    Attributes:
        id (str): A unique response identifier.
        object (str): The type of response.
        created (int): Creation time as a UNIX timestamp.
        model (str): The model used.
        choices (List[OpenAICompletionChoice]): A list of completion choices.
        usage (OpenAIUsage): Token usage statistics.
        system_fingerprint (str): A string fingerprint of the system.
    """
    id: str                                 = Field(..., description="Unique response ID.")
    object: str                             = Field("text_completion", description="Response type.")
    created: int                            = Field(..., description="Creation timestamp (UNIX epoch).")
    model: str                              = Field(..., description="The model used.")
    choices: List[OpenAICompletionChoice]   = Field(..., description="List of completion choices.")
    usage: OpenAIUsage                      = Field(..., description="Token usage details.")
    system_fingerprint: str                 = Field(..., description="System fingerprint for tracking.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "cmpl-1234567890",
                "object": "text_completion",
                "created": 1696147200,
                "model": "nemo",
                "choices": [
                    {
                        "text": "The weather is sunny and warm.",
                        "index": 0,
                        "logprobs": None,
                        "finish_reason": "stop"
                    }
                ],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 20,
                    "total_tokens": 30
                },
                "system_fingerprint": "fingerprint_string"
            }
        }
    }


class ChatCompletionRequest(BaseModel):
    """
    Represents an OpenAI-compatible chat completion request.
    
    Attributes:
        model (str): The model to use (e.g. "nemo").
        messages (List[ChatMessage]): The conversation history (only user and assistant messages will be used).
        temperature (Optional[float]): Sampling temperature (default: 0.7).
        max_tokens (Optional[int]): Maximum tokens for the completion (default: 256).
    """
    model: str                          = Field(LLM_DEFAULTS['model'], description="The model to be used, e.g. 'nemo'.")
    messages: List[ChatMessage]         = Field(..., description="A list of messages representing the conversation history.")
    temperature: Optional[float]        = Field(LLM_DEFAULTS['temperature'], description="Sampling temperature.")
    max_tokens: Optional[int]           = Field(LLM_DEFAULTS['max_tokens'], description="Maximum tokens for completion.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "model": "nemo",
                "messages": [
                    {"role": "user", "content": "What's the weather like today?"},
                    {"role": "assistant", "content": "It's sunny and warm."}
                ],
                "temperature": 0.7,
                "max_tokens": 256
            }
        },
        "extra": "allow"
    }


class ChatCompletionChoice(BaseModel):
    """
    Represents an individual choice in the OpenAI chat completion response.
    
    Attributes:
        index (int): The index of the choice.
        message (ChatMessage): The generated message.
        finish_reason (Optional[str]): The reason for finishing the completion.
    """
    index: int                          = Field(..., description="Index of the completion choice.")
    message: ChatMessage                = Field(..., description="Generated message.")
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
