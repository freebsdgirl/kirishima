from app.services.dm import _send_dm

from shared.models.discord import SendDMRequest

from shared.log_config import get_logger
logger = get_logger(f"discord.{__name__}")

from fastapi import APIRouter, Request
router = APIRouter()


@router.post("/dm", response_model=dict, status_code=200)
async def send_dm(request: Request, payload: SendDMRequest) -> dict:
    """
    FastAPI endpoint to send a direct message (DM) to a specified Discord user.

    Args:
        request (Request): The FastAPI request object containing the bot state.
        payload (SendDMRequest): A request payload containing the target user ID and message content.

    Returns:
        dict: A status response indicating successful message delivery.

    Raises:
        HTTPException: 404 if the user is not found, 500 for other sending errors.
    """
    return await _send_dm(request, payload)