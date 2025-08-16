from fastapi import APIRouter, HTTPException
from shared.models.ledger import ToolSyncRequest, AssistantSyncRequest
from app.services.sync.tool import _sync_tool_buffer_helper
from app.services.sync.assistant import _sync_assistant_buffer_helper

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
