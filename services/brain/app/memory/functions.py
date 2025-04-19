"""
This module provides FastAPI endpoints for creating and deleting memory entries 
in the ChromaDB service. It interacts with external services such as the brain 
service for retrieving the current mode and ChromaDB for embedding generation 
and memory storage.
Functions:
    create_memory(request: MemoryEntry) -> MemoryEntryFull:
        Creates a new memory entry by retrieving the current mode, generating 
        an embedding, and storing the memory in ChromaDB.
    delete_memory(request: MemoryEntry):
        Deletes a specific memory entry from ChromaDB based on the provided 
        memory content and mode.
Dependencies:
    - shared.consul: For retrieving service addresses.
    - shared.log_config: For logging configuration.
    - shared.models.chromadb: For memory entry models.
    - httpx: For making asynchronous HTTP requests.
    - fastapi: For defining API routes and handling HTTP exceptions.
"""

import shared.consul

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from shared.models.chromadb import MemoryEntry, MemoryEntryFull


import httpx
from fastapi import APIRouter, HTTPException, status, Body
router = APIRouter()


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

    async with httpx.AsyncClient(timeout=60) as client:
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

        async with httpx.AsyncClient() as client:
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


@router.delete("/memory", response_model=dict, status_code=200)
async def delete_memory(request: MemoryEntry = Body(...)):
    """
    Delete a specific memory entry from ChromaDB based on memory content and mode.

    Attempts to find and delete the first memory entry matching the provided memory and mode.
    Returns the id of the deleted memory if found and deleted, or 404 if not found.
    Raises an HTTPException if the ChromaDB service is unavailable or if there are errors during the deletion process.

    Args:
        request (MemoryEntry): The memory entry to be deleted, containing memory content and mode.

    Raises:
        HTTPException: If ChromaDB service is unavailable or deletion fails.
    """
    logger.debug(f"/memory DELETE Request: memory={request.memory}, mode={request.mode}")

    try:
        chromadb_host, chromadb_port = shared.consul.get_service_address('chromadb')
        if not chromadb_host or not chromadb_port:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="ChromaDB service is unavailable."
            )

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://{chromadb_host}:{chromadb_port}/memory",
                params={"mode": request.mode}
            )

            if response.status_code != 200:
                logger.error(f"Failed to search memories: {response.status_code} {response.text}")

                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to search for memories."
                )
            memories = response.json()

            matches = [m for m in memories if m["memory"] == request.memory and m["metadata"]["mode"] == request.mode]

            if not matches:
                logger.info("No matching memories found to delete.")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No matching memory found to delete."
                )

            # Only delete the first match
            m = matches[0]
            mem_id = m["id"]
            del_resp = await client.delete(f"http://{chromadb_host}:{chromadb_port}/memory/{mem_id}")

            if del_resp.status_code != status.HTTP_204_NO_CONTENT:
                logger.error(f"Failed to delete memory id={mem_id}: {del_resp.status_code} {del_resp.text}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete memory id={mem_id}."
                )
            return {"id": mem_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"An error occurred while deleting memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting memory: {e}"
        )
