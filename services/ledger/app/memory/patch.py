"""
This module provides functionality to update existing memory records in the database via a PATCH endpoint.
Functions:
    _memory_patch(memory: MemoryEntry):
        Updates an existing memory and its tags in the memories database. Returns True if updated, raises HTTPException on error.
    memory_patch(memory: MemoryEntry):
        FastAPI route handler for PATCH /memories.
        Validates input, checks for memory existence, and ensures at least one field is provided for update.
        Returns a status dictionary on success or raises HTTPException on error.
Dependencies:
    - shared.log_config.get_logger: For logging.
    - shared.models.ledger.MemoryEntry: Memory model.
    - app.util._open_conn: Database connection utility.
    - app.memory.util.memory_exists: Checks if a memory exists.
    - sqlite3, json: For database and serialization.
    - fastapi.APIRouter, HTTPException, status, Query: FastAPI utilities.
"""
from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from shared.models.ledger import MemoryEntry

from app.util import _open_conn
from app.memory.util import memory_exists

import sqlite3
import json

from fastapi import APIRouter, HTTPException, status, Query
router = APIRouter()


def _memory_patch(memory: MemoryEntry):
    """
    Update an existing memory and its tags in the memories database. Returns True if updated, raises HTTPException on error.
    """
    try:
        with _open_conn() as conn:
            cursor = conn.cursor()
            update_fields = []
            update_values = []
            if memory.memory is not None:
                update_fields.append("memory = ?")
                update_values.append(memory.memory)
            if memory.keywords is not None:
                update_fields.append("keywords = ?")
                update_values.append(json.dumps(memory.keywords))
            if memory.category is not None:
                update_fields.append("category = ?")
                update_values.append(memory.category)
            if not update_fields:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No fields to update."
                )
            update_values.append(memory.id)
            update_query = f"UPDATE memories SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(update_query, tuple(update_values))
            conn.commit()
            if cursor.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No memory found with that ID."
                )
        logger.debug(f"Memory ID {memory.id} updated successfully.")
        return True
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )


@router.patch("/memories/by-id/{memory_id}")
def memory_patch(memory_id: str, memory: MemoryEntry):
    """
    Updates an existing memory record in the database with new information.
    Args:
        memory (Memory): An object containing updated memory data, including optional fields
            such as keywords, category, and memory content.
    Raises:
        HTTPException: If the memory ID is not provided.
        HTTPException: If none of the fields (keywords, category, memory) are provided for update.
    Returns:
        dict: A dictionary containing the status of the operation and the memory ID.
    """
    logger.debug(f"PATCH /memories Request: memory_id={memory.id}, memory={memory.memory}, keywords={memory.keywords}, category={memory.category}")

    if not memory.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Memory ID must be provided."
        )
    
    if not memory_exists(memory.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory ID {memory.id} not found."
        )

    if not memory.keywords and not memory.category and not memory.memory:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of keywords, category, or memory must be provided."
        )
    
    try:
        updated = _memory_patch(memory)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update memory."
            )
        logger.info(f"Memory ID {memory.id} updated successfully.")
    except HTTPException as e:
        logger.error(f"Error updating memory ID {memory.id}: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Internal server error while updating memory ID {memory.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while updating the memory."
        )

    return {"status": "success", "id": memory.id}
