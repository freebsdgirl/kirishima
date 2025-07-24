"""
Health check routes for Discord service.
"""
from fastapi import APIRouter, Request
from shared.log_config import get_logger

logger = get_logger(f"discord.{__name__}")
router = APIRouter()


@router.get("/health", response_model=dict, status_code=200)
async def health_check(request: Request) -> dict:
    """
    Health check endpoint that reports Discord bot status.
    
    Args:
        request (Request): FastAPI request object containing app state
        
    Returns:
        dict: Health status including bot connection state
    """
    bot = request.app.state.bot
    
    return {
        "status": "healthy",
        "bot_ready": bot.is_ready() if bot else False,
        "bot_logged_in": not bot.is_closed() if bot else False,
        "service": "discord"
    }
