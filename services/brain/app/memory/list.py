import shared.consul

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from shared.models.chromadb import MemoryEntry, MemoryEntryFull


import httpx
from fastapi import APIRouter, HTTPException, status, Body
router = APIRouter()


# list all memories for a component and/or mode
# mode is optional, component is required.

@router.get("/memory", response_model=list[MemoryEntryFull])
async def list_memory():
    pass