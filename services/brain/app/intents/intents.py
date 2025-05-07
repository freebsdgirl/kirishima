from fastapi import HTTPException, status
from shared.models.intents import IntentRequest
from shared.models.proxy import ChatMessage

from app.intents.mode import process_mode
from app.intents.memory import process_memory

from typing import List

from shared.log_config import get_logger
logger = get_logger(f"intents.{__name__}")


async def process_intents(payload: IntentRequest) -> List[ChatMessage]:
    """
    Process intents from an IntentRequest payload by executing mode and memory processing.
    
    This async function handles intent processing by:
    1. Validating the payload has at least one intent flag set
    2. Extracting the last message from the payload
    3. Optionally processing mode-related intent modifications
    4. Optionally processing memory-related intent modifications
    
    Args:
        payload (IntentRequest): The intent request containing mode, memory, and message flags
    
    Returns:
        List[ChatMessage]: The processed list of messages, with potential modifications
    
    Raises:
        HTTPException: If payload validation fails or processing encounters an error
    """
    logger.debug(f"/intents Request:\n{payload.model_dump_json(indent=4)}")

    if not (payload.mode or payload.memory):
        logger.debug(f"IntentRequest: no payload flags set to true: {payload}")

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one intent flag must be set to true."
        )

    if payload.message:
        last_message: ChatMessage = payload.message[-1]
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No messages in payload.message"
        )
     
    # Get the last 10 messages (or fewer, if there aren’t 10 yet)
    # last_ten: list[ProxyMessage] = payload.message[-10:]

    if payload.mode:
        try:
            last_message = process_mode(last_message)
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
            last_message = await process_memory(last_message, payload.component)
            payload.message[-1] = last_message
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error in memory processing: {e}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error in memory: {e}"
            )

    return payload.message
