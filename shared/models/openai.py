from typing import List, Optional, Literal
from pydantic import BaseModel, Field, Extra

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


class ChatMessage(BaseModel):
    """
    Represents a message in an OpenAI chat conversation.
    
    Attributes:
        role (str): The role of the message sender; one of "user" or "assistant".
        content (str): The message content.
    """
    role: Literal["user", "assistant", "system"] = Field(..., description="The role of the message sender.")
    content: str = Field(..., description="The textual content of the message.")


class ChatCompletionRequest(BaseModel):
    """
    Represents an OpenAI-compatible chat completion request.
    
    Attributes:
        model (str): The model to use (e.g. "nemo").
        messages (List[ChatMessage]): The conversation history (only user and assistant messages will be used).
        temperature (Optional[float]): Sampling temperature (default: 0.7).
        max_tokens (Optional[int]): Maximum tokens for the completion (default: 256).
    """
    model: str = Field(..., description="The model to be used, e.g. 'nemo'.")
    messages: List[ChatMessage] = Field(..., description="A list of messages representing the conversation history.")
    temperature: Optional[float] = Field(0.7, description="Sampling temperature.")
    max_tokens: Optional[int] = Field(256, description="Maximum tokens for completion.")

    class Config:
        json_schema_extra = {
            "example": {
                "model": "nemo",
                "messages": [
                    {"role": "user", "content": "What's the weather like today?"},
                    {"role": "assistant", "content": "It's sunny and warm."}
                ],
                "temperature": 0.7,
                "max_tokens": 256
            }
        }
        extra = Extra.allow


class ChatCompletionChoice(BaseModel):
    """
    Represents an individual choice in the OpenAI chat completion response.
    
    Attributes:
        index (int): The index of the choice.
        message (ChatMessage): The generated message.
        finish_reason (Optional[str]): The reason for finishing the completion.
    """
    index: int = Field(..., description="Index of the completion choice.")
    message: ChatMessage = Field(..., description="Generated message.")
    finish_reason: Optional[str] = Field("stop", description="Reason for finishing the completion.")


class ChatUsage(BaseModel):
    """
    Represents token usage information.
    
    Attributes:
        prompt_tokens (int): Number of tokens in the prompt.
        completion_tokens (int): Number of tokens generated.
        total_tokens (int): Total tokens used.
    """
    prompt_tokens: int = Field(..., description="Tokens in the prompt.")
    completion_tokens: int = Field(..., description="Tokens in the completion.")
    total_tokens: int = Field(..., description="Total tokens used.")


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
    id: str = Field(..., description="Unique response ID.")
    object: str = Field("chat.completion", description="Response type.")
    created: int = Field(..., description="Creation timestamp (UNIX epoch).")
    model: str = Field(..., description="The model used.")
    choices: List[ChatCompletionChoice] = Field(..., description="List of completion choices.")
    usage: ChatUsage = Field(..., description="Token usage details.")
