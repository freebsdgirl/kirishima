from app.services.chat_completions import _chat_completions
from app.services.completions import _completions
from app.services.util import _resolve_model_provider_options

from shared.models.proxy import ProxyOneShotRequest, ProxyResponse, MultiTurnRequest, SingleTurnRequest
from typing import Union

from fastapi import APIRouter

router = APIRouter()
@router.post("/api/singleturn", response_model=ProxyResponse)
async def completions(message: Union[ProxyOneShotRequest, SingleTurnRequest]) -> ProxyResponse:
    """
    Handle single-turn language model completion requests.

    This endpoint accepts either a ProxyOneShotRequest (explicit model/provider) or 
    a SingleTurnRequest (mode-based resolution), resolves the appropriate provider,
    constructs the request, enqueues it, and returns the response as a ProxyResponse.

    Args:
        message (Union[ProxyOneShotRequest, SingleTurnRequest]): The completion request.
            - ProxyOneShotRequest: Contains explicit model, prompt, temperature, max_tokens, provider
            - SingleTurnRequest: Contains mode name and prompt, resolves config from config.json

    Returns:
        ProxyResponse: The response from the language model, including generated
            text, token count, and timestamp.

    Raises:
        HTTPException: If there are connection or communication errors with the model service.
    """
    # Diverging logic based on request type
    if isinstance(message, SingleTurnRequest):
        # Mode-based resolution: resolve actual model/provider/options from config.json
        provider, actual_model, options = _resolve_model_provider_options(message.model)
        
        # Convert SingleTurnRequest to ProxyOneShotRequest with resolved values
        proxy_request = ProxyOneShotRequest(
            model=actual_model,
            prompt=message.prompt,
            temperature=options.get('temperature', 0.7),
            max_tokens=options.get('max_tokens', 256),
            provider=provider
        )
        return await _completions(proxy_request)
    else:
        # ProxyOneShotRequest: use as-is (explicit model/provider)
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