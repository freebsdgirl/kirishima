from fastapi import APIRouter, HTTPException
from shared.models.ledger import ToolSyncRequest, AssistantSyncRequest, UserSyncRequest, CanonicalUserMessage
from app.services.sync.tool import _sync_tool_buffer_helper
from app.services.sync.assistant import _sync_assistant_buffer_helper
from app.services.sync.user import _sync_user_buffer_helper
from app.services.sync.get import _get_sync_buffer_helper
from typing import List, Optional

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

router = APIRouter()

@router.post("/tool")
async def sync_tool(request: ToolSyncRequest):
    """
    Endpoint for synchronizing tool calls and outputs.
    """
    try:
        _sync_tool_buffer_helper(request)
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Failed to sync tool: {e}")
        raise HTTPException(status_code=503, detail=f"Database error: {e}")

@router.post("/assistant")
async def sync_assistant(request: AssistantSyncRequest):
    """
    Endpoint for synchronizing assistant messages.
    """
    try:
        _sync_assistant_buffer_helper(request)
        return {"status": "success"}
    except ValueError as e:
        logger.error(f"Invalid assistant sync request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to sync assistant: {e}")
        raise HTTPException(status_code=503, detail=f"Database error: {e}")


@router.post("/user")
async def sync_user(request: UserSyncRequest):
    """
    Endpoint for synchronizing user messages.
    """
    try:
        _sync_user_buffer_helper(request)
        return {"status": "success"}
    except ValueError as e:
        logger.error(f"Invalid user sync request: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to sync user: {e}")
        raise HTTPException(status_code=503, detail=f"Database error: {e}")

@router.get("/get", response_model=List[CanonicalUserMessage])
async def get_sync_buffer(user_id: Optional[str] = None):
    """
    Endpoint for retrieving the conversation buffer with token-based limiting.
    
    Returns the conversation history up to the configured token limit,
    ensuring the first message is a user message.
    """
    try:
        messages = _get_sync_buffer_helper(user_id)
        return messages
    except Exception as e:
        logger.error(f"Failed to get sync buffer: {e}")
        raise HTTPException(status_code=503, detail=f"Database error: {e}")
