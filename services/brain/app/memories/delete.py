"""
This module provides an API endpoint for deleting memory entries via the ledger service.

Functions:
    memory_delete(memory_id: str) -> dict:
        Deletes a memory entry via the ledger service using the provided memory ID.
"""
from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import httpx
import json
import os

from fastapi import APIRouter, HTTPException, status, Query
router = APIRouter()

@router.delete("/memories/delete", response_model=dict)
async def memory_delete(
    memory_id: str = Query(..., description="The ID of the memory to delete.")
):
    """
    Deletes a memory entry via the ledger service.

    Args:
        memory_id (str): The ID of the memory to delete. Provided as a query parameter.

    Returns:
        dict: A dictionary containing the status of the deletion and the ID of the deleted memory.

    Raises:
        HTTPException: 
            - 404 Not Found: If no memory with the specified ID exists.
            - 500 Internal Server Error: If an error occurs during the deletion process.
    """
    logger.debug(f"DELETE /memories/delete Request: memory_id={memory_id}")
    
    try:
        # Call ledger service
        ledger_port = os.getenv("LEDGER_PORT", 4203)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.delete(
                f'http://ledger:{ledger_port}/memories/by-id/{memory_id}'
            )
            
            if response.status_code == 404:
                logger.debug(f"Memory ID {memory_id} not found for deletion.")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No memory found with that ID."
                )
            
            response.raise_for_status()
            result = response.json()
            logger.debug(f"Memory ID {memory_id} deleted successfully.")
            return result
            
    except httpx.TimeoutException:
        logger.error("Request to ledger service timed out")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Memory deletion request timed out"
        )
    except httpx.RequestError as e:
        logger.error(f"Error calling ledger service: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error deleting memory: {str(e)}"
        )
    except HTTPException:
        raise  # Re-raise HTTPException as-is
    except Exception as e:
        logger.error(f"Unexpected error in memory delete: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )