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

from typing import List, Optional, Dict
from pydantic import BaseModel, Field

import os
import json

CONFIG_PATH = os.environ.get("KIRISHIMA_CONFIG", "/app/config/config.json")
with open(CONFIG_PATH) as f:
    _config = json.load(f)
_default_mode = _config["llm"]["mode"]["default"]

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
    model: Optional[str]                = Field(_default_mode['model'], description="The model to be used.")
    temperature: Optional[float]        = Field(..., description="Sampling temperature.")
    max_tokens: Optional[int]           = Field(..., description="Maximum tokens to generate.")
    n: Optional[int]                    = Field(default=1, description="Number of completions to generate.")
    provider: Optional[str]             = Field("openai", description="The provider of the model, default is 'ollama'.")

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
        content (str): The generated response text.
        index (int): The index of the completion.
        logprobs (Optional[dict]): Log probabilities (if available).
        finish_reason (Optional[str]): The reason the completion finished.
    """
    content: str                        = Field(..., description="Generated response text.")
    index: int                          = Field(..., description="Index of the completion choice.")
    logprobs: Optional[dict]            = Field(None, description="Log probabilities (if available).")
    # Note: logprobs is not used in the current implementation, but included for completeness.
    finish_reason: Optional[str]        = Field("stop", description="Reason for finishing the completion.")

    model_config = {
        "json_schema_extra": {
            "example": {
                "content": "The weather is sunny and warm.",
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


