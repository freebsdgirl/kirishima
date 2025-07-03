"""
This module provides an API endpoint and supporting function for updating existing memory records in the memories database.
Functions:
    - update_memory_db(memory_id: str, memory: str = None, keywords: list = None, category: str = None, priority: float = None):
        Updates an existing memory record and its associated fields (memory text, keywords, category, priority) in the database.
        Raises HTTPException on error or if no fields are provided for update.
API Endpoints:
    - PATCH /memories:
        Updates an existing memory and its tags in the memories database.
        Query Parameters:
            - memory_id (str): The ID of the memory to update. (Required)
            - memory (str, optional): The updated memory text.
            - keywords (list, optional): Updated list of tags/keywords associated with the memory.
            - category (str, optional): Updated category associated with the memory.
            - priority (float, optional): Updated priority level for the memory, between 0.0 and 1.0 (default: 0.5).
            - dict: A dictionary containing the status and the updated memory ID.
            - 400 Bad Request: If memory_id is not provided or if no fields are provided for update.
"""
from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

import sqlite3
import json

from fastapi import APIRouter, HTTPException, status, Query
router = APIRouter()


def update_memory_db(memory_id: str, memory: str = None, keywords: list = None, category: str = None, priority: float = None):
    """
    Update an existing memory and its tags in the memories database. Returns True if updated, raises HTTPException on error.
    """
    try:
        with open('/app/config/config.json') as f:
            _config = json.load(f)
        MEMORIES_DB = _config['db']['memories']

        with sqlite3.connect(MEMORIES_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            update_fields = []
            update_values = []
            if memory is not None:
                update_fields.append("memory = ?")
                update_values.append(memory)
            if keywords is not None:
                update_fields.append("keywords = ?")
                update_values.append(json.dumps(keywords))
            if category is not None:
                update_fields.append("category = ?")
                update_values.append(category)
            if priority is not None:
                update_fields.append("priority = ?")
                update_values.append(priority)
            if not update_fields:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No fields to update."
                )
            update_values.append(memory_id)
            update_query = f"UPDATE memories SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(update_query, tuple(update_values))
            conn.commit()
            if cursor.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No memory found with that ID."
                )
        logger.debug(f"Memory ID {memory_id} updated successfully.")
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


@router.patch("/memories")
def memory_patch(
    memory_id: str = Query(..., description="The ID of the memory to update."),
    memory: str = Query(None, description="The updated memory text."),
    keywords: list = Query(None, description="Updated list of tags/keywords associated with the memory."),
    category: str = Query(None, description="Updated category associated with the memory."),
    priority: float = Query(0.5, description="Updated priority level for the memory, between 0.0 and 1.0.")
):
    """
    Update an existing memory and its tags in the memories database.

    Args:
        memory_id (str): The ID of the memory to update.
        memory (str, optional): The updated memory text.
        keywords (list, optional): Updated list of tags/keywords associated with the memory.
        category (str, optional): Updated category associated with the memory.
        priority (float): Updated priority level for the memory, between 0.0 and 1.0.

    Returns:
        dict: A dictionary containing the status and the updated memory ID.
    Raises:
        HTTPException: 
            - 400 Bad Request: If memory_id is not provided or if both keywords and category are not provided.
            - 404 Not Found: If no memory with the specified ID exists.
            - 500 Internal Server Error: If an error occurs during the update process.
    """
    logger.debug(f"PATCH /memories Request: memory_id={memory_id}, memory={memory}, keywords={keywords}, category={category}, priority={priority}")

    if not memory_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Memory ID must be provided."
        )
    
    if not keywords and not category and not priority and not memory:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one of keywords, category, priority, or memory must be provided."
        )
    
    update_memory_db(memory_id, memory, keywords, category, priority)
    return {"status": "success", "memory_id": memory_id}