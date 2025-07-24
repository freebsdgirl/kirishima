from shared.models.discord import SendDMRequest

from shared.log_config import get_logger
logger = get_logger(f"discord.{__name__}")

from fastapi import HTTPException, status, APIRouter, Request
router = APIRouter()


async def _send_dm(request: Request, payload: SendDMRequest) -> dict:
    """
    Send a direct message (DM) to a specified Discord user.

    Args:
        request (Request): The FastAPI request object containing the bot state.
        payload (SendDMRequest): A request payload containing the target user ID and message content.

    Returns:
        dict: A status response indicating successful message delivery.

    Raises:
        HTTPException: 404 if the user is not found, 500 for other sending errors.
    """
    bot = request.app.state.bot

    try:
        user = await bot.fetch_user(payload.user_id)

        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail=f"User not found: {payload.user_id}"
            )
        
        await user.send(payload.content)
        
        return {
            "status": "success",
            "message": f"DM sent to user {payload.user_id}"}

    except Exception as e:
        logger.exception(f"Failed to send DM to {payload.user_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )