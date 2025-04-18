from fastapi import APIRouter, HTTPException, status
from shared.models.intents import IntentRequest
from shared.models.proxy import ProxyMessage

from app.mode import process_mode
from app.memory import process_memory

from typing import List

from shared.log_config import get_logger
logger = get_logger(f"intents.{__name__}")

router = APIRouter()


@router.post("/intents", response_model=List[ProxyMessage])
async def process_intents(payload: IntentRequest) -> List[ProxyMessage]:
    """
    Process intents by handling mode and memory operations for the last message in a payload.

    This endpoint validates the intent request, processes mode and memory flags if set,
    and updates the last message accordingly. Raises HTTP exceptions for invalid payloads
    or processing errors.

    Args:
        payload (IntentRequest): The intent request containing mode, memory, and message flags.

    Returns:
        IntentRequest: The modified payload with processed last message.

    Raises:
        HTTPException: 400 if no intent flags are set or no messages exist,
                    500 if errors occur during mode or memory processing.
    """

    if not (payload.mode or payload.memory):
        logger.debug(f"IntentRequest: no payload flags set to true: {payload}")

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one intent flag must be set to true."
        )

    if payload.message:
        last_message: ProxyMessage = payload.message[-1]
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No messages in payload.message"
        )
     
    # Get the last 10 messages (or fewer, if there aren’t 10 yet)
    # last_ten: list[ProxyMessage] = payload.message[-10:]

    if payload.mode:
        try:
            last_message = await process_mode(last_message)
            payload.message[-1] = last_message

        except HTTPException:
            raise
        except Exception as e:
            logger.error

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error in mode: {e}"
            )

    if payload.memory:
        try:
            last_message = await process_memory(last_message)
            payload.message[-1] = last_message
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in memory processing: {e}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error in memory: {e}"
            )

    return payload.message  # Return the modified payload object
