"""
Media tracking routes for logging music, TV, and movie consumption.
Provides webhooks that Home Assistant can call when media state changes.
"""
from shared.models.smarthome import MediaEvent

from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from app.services.media import _track_media_event, _get_media_stats
from shared.log_config import get_logger

logger = get_logger(f"smarthome.{__name__}")

router = APIRouter()


@router.post("/media_event")
async def track_media_event(event: MediaEvent) -> Dict[str, Any]:
    """
    Track a media event from Home Assistant or Music Assistant.
    
    This endpoint is designed to be called by Home Assistant automations
    whenever media state changes on any device.
    """
    try:
        return await _track_media_event(event)
    except Exception as e:
        logger.exception(f"Error in media event endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to track media event: {str(e)}"
        )


@router.get("/media_stats")
async def get_media_stats() -> Dict[str, Any]:
    """Get summary statistics about tracked media consumption."""
    try:
        return await _get_media_stats()
    except Exception as e:
        logger.exception(f"Error in media stats endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get media stats: {str(e)}"
        )
from app.services.media import _track_media_event, _get_media_stats

from shared.models.smarthome import MediaEvent

from typing import Dict, Any

from shared.log_config import get_logger
logger = get_logger(f"smarthome.{__name__}")

from fastapi import APIRouter
router = APIRouter()


@router.post("/media_event")
async def track_media_event(event: MediaEvent) -> Dict[str, Any]:
    return await _track_media_event(event)


@router.get("/media_stats")
async def get_media_stats() -> Dict[str, Any]:
    return await _get_media_stats()

