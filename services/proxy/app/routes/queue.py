from fastapi import APIRouter, HTTPException
from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

router = APIRouter()

@router.get("/{path:path}")
async def queue_removed(path: str):
    logger.warning("Queue endpoint accessed after removal: /queue/%s", path)
    raise HTTPException(status_code=410, detail="Queue system removed. Use direct /api endpoints.")