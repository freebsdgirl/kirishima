from typing import List, Optional
from pydantic import BaseModel, Field

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
    prompt: str
    model: Optional[str] = Field(default="nemo")
    temperature: Optional[float] = Field(default=0.7)
    max_tokens: Optional[int] = Field(default=256)
    n: Optional[int] = Field(default=1)


class OpenAICompletionChoice(BaseModel):
    """
    Represents an individual completion choice in the OpenAI-style response.
    
    Attributes:
        text (str): The generated response text.
        index (int): The index of the completion.
        logprobs (Optional[dict]): Log probabilities (if available).
        finish_reason (Optional[str]): The reason the completion finished.
    """
    text: str
    index: int
    logprobs: Optional[dict] = None
    finish_reason: Optional[str] = "stop"


class OpenAIUsage(BaseModel):
    """
    Represents usage statistics in the OpenAI-style response.
    
    Attributes:
        prompt_tokens (int): Number of tokens in the prompt.
        completion_tokens (int): Number of tokens generated as completion.
        total_tokens (int): Total tokens counted (prompt + completion).
    """
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


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
    id: str
    object: str = "text_completion"
    created: int
    model: str
    choices: List[OpenAICompletionChoice]
    usage: OpenAIUsage
    system_fingerprint: str