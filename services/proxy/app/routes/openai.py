from app.services.chat_completions import _chat_completions
from app.services.completions import _completions

from shared.models.proxy import ProxyOneShotRequest, ProxyResponse, MultiTurnRequest

from fastapi import APIRouter

router = APIRouter()
@router.post("/api/singleturn", response_model=ProxyResponse)
async def completions(message: ProxyOneShotRequest) -> ProxyResponse:
    """
    Handle single-turn language model completion requests.

    This endpoint accepts a ProxyOneShotRequest, resolves the appropriate provider,
    constructs the request, enqueues it, and returns the response as a ProxyResponse.

    Args:
        message (ProxyOneShotRequest): The completion request containing model, prompt,
            temperature, and max tokens parameters.

    Returns:
        ProxyResponse: The response from the language model, including generated
            text, token count, and timestamp.

    Raises:
        HTTPException: If there are connection or communication errors with the model service.
    """
    return await _completions(message)


@router.post("/api/multiturn", response_model=ProxyResponse)
async def chat_completions(request: MultiTurnRequest) -> ProxyResponse:
    """
    Handle multi-turn API requests by generating prompts for language models.

    Processes a multi-turn conversation request, validates model compatibility,
    builds an instruct-style prompt, and sends a request to the Ollama API.
    Returns a ProxyResponse with the generated text and metadata.

    Args:
        request (MultiTurnRequest): Multi-turn conversation request details.

    Returns:
        ProxyResponse: Generated response from the language model.

    Raises:
        HTTPException: If the model is not instruct-compatible or API request fails.
    """
    
    return await _chat_completions(request)