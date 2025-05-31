"""
This module provides an API endpoint for creating new memory entries in the brain service.
It defines a FastAPI router with a POST endpoint `/memory` that:
- Retrieves the current mode from the brain service.
- Generates an embedding for the provided memory entry using ChromaDB.
- Stores the complete memory entry, including the mode and embedding, in ChromaDB.
Dependencies:
    - shared.config: Provides configuration constants such as TIMEOUT.
    - shared.consul: Service discovery for retrieving service addresses.
    - shared.models.memory: Data models for memory entries.
    - shared.log_config: Logger configuration.
    - httpx: For making asynchronous HTTP requests.
    - fastapi: For API routing and exception handling.
    HTTPException: For errors in service communication, embedding generation, or memory storage.
"""

import shared.consul

from shared.models.memory import MemoryEntry, MemoryEntryFull

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx
import json

from fastapi import APIRouter, HTTPException, status
router = APIRouter()

with open('/app/shared/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]


@router.post("/memory", response_model=MemoryEntryFull)
async def create_memory(request: MemoryEntry) -> MemoryEntryFull:
    """
    Create a new memory entry with mode and embedding.

    Creates a memory entry by retrieving the current mode from the brain service,
    generating an embedding for the memory using ChromaDB, and then storing the
    complete memory entry in ChromaDB.

    Args:
        request (MemoryEntry): The memory entry to be created.

    Returns:
        MemoryEntryFull: The fully populated memory entry after successful creation.

    Raises:
        HTTPException: If there are issues retrieving mode, generating embedding,
        or storing the memory in ChromaDB.
    """
    logger.debug(f"/memory/create Request:\n{request.model_dump_json(indent=4)}")

    payload = request.model_dump()

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        brain_address, brain_port = shared.consul.get_service_address('brain')
        
        response = await client.get(f"http://{brain_address}:{brain_port}/mode")
        response.raise_for_status()

        json_response = response.json()
        mode = json_response.get("message", None)

    payload["mode"] = mode

    try:
        chromadb_host, chromadb_port = shared.consul.get_service_address('chromadb')
        if not chromadb_host or not chromadb_port:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ChromaDB service is unavailable."
            )

        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                f"http://{chromadb_host}:{chromadb_port}/embedding",
                json={"input": payload['memory']}
            )

        if response.status_code != status.HTTP_200_OK:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Embedding model error"
            )

        payload["embedding"] = response.json()

    except Exception as e:
        logger.error(f"Error creating embedding: {e}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating embedding: {e}"
        )
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
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
                detail=f"Failed to create memory: {e.response.status_code} {e.response.text}"
            )

        except Exception as e:
            logger.error(f"An error occurred while creating memory: {e}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create memory: {e}"
            )

    return MemoryEntryFull(**response.json())
