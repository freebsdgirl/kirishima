"""
This module defines the FastAPI router and logic for processing intent requests.

Classes:
    None

Functions:
    process_intents(payload: IntentRequest) -> dict:
        Handles POST requests to the `/intents` endpoint. Processes intent flags
        provided in the request payload by delegating to the appropriate handler
        functions.

Constants:
    _INTENT_HANDLERS: dict[str, Callable[[], int | None]]:
        A mapping of intent flag names to their respective handler functions.
        Each handler is expected to return either an HTTP status code or None.

Routes:
    POST /intents:
        Processes intent flags provided in the request payload. At least one
        intent flag must be set to `true`. If an unknown intent is provided or
        an error occurs during processing, an appropriate HTTPException is raised.
"""
import app.mode

from fastapi import APIRouter, HTTPException, status
from shared.models.intents import IntentRequest
from typing import Callable


router = APIRouter()


# map each flag name to its handler
_INTENT_HANDLERS: dict[str, Callable[[], int | None]] = {
    "mode": app.mode.process_mode,
    # "sync": app.sync.process_sync,
    # "cleanup": app.cleanup.process_cleanup,
}


@router.post("/intents", response_model=dict)
async def process_intents(payload: IntentRequest) -> dict:
    """
    Handles POST requests to the `/intents` endpoint by processing intent flags.

    Validates that at least one intent flag is set to true, then iterates through
    requested intents and calls their corresponding handler functions. Raises
    appropriate HTTPExceptions for various error conditions.

    Args:
        payload (IntentRequest): Request payload containing intent flags.

    Returns:
        dict: A response indicating successful processing of all requested intents.

    Raises:
        HTTPException: For various error scenarios such as no intents set,
        unknown intents, or handler-specific errors.
    """
    requested = [name for name, value in payload.model_dump().items() if value]
    if not requested:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one intent flag must be set to true."
        )

    for intent in requested:
        handler = _INTENT_HANDLERS.get(intent)
        if handler is None:
            # unknown intent; skip or error out:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"No handler configured for intent '{intent}'."
            )

        try:
            result = handler()
            # if handler returns an HTTP status code, check it
            if isinstance(result, int) and result != status.HTTP_200_OK:
                raise HTTPException(
                    status_code=result,
                    detail=f"Handler for '{intent}' returned status {result}."
                )

        except HTTPException:
            # forward any HTTPException from the handler immediately
            raise
        except Exception as e:
            # catch-all for anything unexpected
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error processing '{intent}': {e}"
            )

    return {"detail": "All requested intents processed successfully"}
