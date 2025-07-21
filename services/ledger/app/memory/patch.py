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

from fastapi import APIRouter, HTTPException, status, Query
router = APIRouter()


def _memory_patch(memory: MemoryEntry):
    """
    Update an existing memory and its tags in the memories database. Returns True if updated, raises HTTPException on error.
    """
    try:
        with _open_conn() as conn:
            cursor = conn.cursor()
            
            # Update memory content if provided
            memory_updated = False
            if memory.memory is not None:
                cursor.execute("UPDATE memories SET memory = ? WHERE id = ?", (memory.memory, memory.id))
                if cursor.rowcount > 0:
                    memory_updated = True
            
            # Update keywords if provided (handle memory_tags table)
            if memory.keywords is not None:
                # Delete existing tags for this memory
                cursor.execute("DELETE FROM memory_tags WHERE memory_id = ?", (memory.id,))
                
                # Insert new tags
                for tag in memory.keywords:
                    tag_lower = tag.lower()
                    cursor.execute(
                        "INSERT OR IGNORE INTO memory_tags (memory_id, tag) VALUES (?, ?)",
                        (memory.id, tag_lower)
                    )
                memory_updated = True
            
            # Update category if provided (handle memory_category table)
            if memory.category is not None:
                # Delete existing category for this memory
                cursor.execute("DELETE FROM memory_category WHERE memory_id = ?", (memory.id,))
                
                # Insert new category
                allowed_categories = [
                    "Health", "Career", "Family", "Personal", "Technical Projects",
                    "Social", "Finance", "Self-care", "Environment", "Hobbies",
                    "Admin", "Philosophy"
                ]
                if memory.category in allowed_categories:
                    cursor.execute(
                        "INSERT INTO memory_category (memory_id, category) VALUES (?, ?)",
                        (memory.id, memory.category)
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid category: {memory.category}. Allowed categories are: {', '.join(allowed_categories)}"
                    )
                memory_updated = True
            
            if not memory_updated:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No fields to update."
                )
            
            conn.commit()
            
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


@router.patch("/memories/{memory_id}")
def memory_patch(memory_id: str, memory: MemoryEntry):
    """
    Updates an existing memory record in the database with new information.
    Args:
        memory_id (str): The ID of the memory to update.
        memory (Memory): An object containing updated memory data, including optional fields
            such as keywords, category, and memory content.
    Raises:
        HTTPException: If the memory ID is not provided.
        HTTPException: If none of the fields (keywords, category, memory) are provided for update.
    Returns:
        dict: A dictionary containing the status of the operation and the memory ID.
    """
    # Use the URL parameter as the memory ID
    memory.id = memory_id
    logger.debug(f"PATCH /memories/{memory_id} Request: memory={memory.memory}, keywords={memory.keywords}, category={memory.category}")

    if not memory_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Memory ID must be provided."
        )
    
    if not memory_exists(memory_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Memory ID {memory_id} not found."
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
        logger.info(f"Memory ID {memory_id} updated successfully.")
    except HTTPException as e:
        logger.error(f"Error updating memory ID {memory_id}: {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Internal server error while updating memory ID {memory_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while updating the memory."
        )

    return {"status": "success", "id": memory_id}
