import shared.consul

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from shared.models.chromadb import MemoryEntry, MemoryEntryFull
from shared.models.proxy import ProxyMessage
from shared.models.embedding import EmbeddingRequest

from app.modes import mode_get
from app.embedding import embedding

import httpx
from fastapi import APIRouter, HTTPException, status
router = APIRouter()

@router.post("/memory/create")
async def create_memory(request: MemoryEntry) -> MemoryEntryFull:
    """
    Creates a memory entry in the ChromaDB collection.

    Args:
        request (MemoryEntry): The memory entry to be created.

    Raises:
        HTTPException: If any error occurs when contacting the ChromaDB service.
    """
    logger.debug(f"/memory/create Request:\n{request.model_dump_json(indent=4)}")

    payload = request.model_dump()

    # populate the mode and the embedding
    # Get mode from brain.
    async with httpx.AsyncClient(timeout=60) as client:
        brain_address, brain_port = shared.consul.get_service_address('brain')
        
        response = await client.get(f"http://{brain_address}:{brain_port}/mode")
        response.raise_for_status()

        json_response = response.json()
        mode = json_response.get("message", None)

    payload["mode"] = mode

    # Get embedding from chroma
    try:
        chromadb_host, chromadb_port = shared.consul.get_service_address('chromadb')
        if not chromadb_host or not chromadb_port:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ChromaDB service is unavailable."
            )

        async with httpx.AsyncClient() as client:
            # Send the memory string as the 'input' field in a JSON object
            response = await client.post(
                f"http://{chromadb_host}:{chromadb_port}/embedding",
                json={"input": payload['memory']}  # Send as EmbeddingRequest
            )

        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Embedding model error"
            )

        payload["embedding"] = response.json()

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating embedding: {e}"
        )
    
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            chromadb_address, chromadb_port = shared.consul.get_service_address('chromadb')
            if not chromadb_address or not chromadb_port:
                logger.error("ChromaDB service address or port is not available.")

                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="ChromaDB service is unavailable."
                )

            response = await client.post(f"http://{chromadb_address}:{chromadb_port}/memory", json=payload)
            response.raise_for_status()
    
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred while creating memory: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create memory."
            )
        except Exception as e:
            logger.error(f"An error occurred while creating memory: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create memory."
            )

    return MemoryEntryFull(**response.json())