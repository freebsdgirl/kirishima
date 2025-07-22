from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from shared.models.ledger import MemoryEntry

from app.util import _open_conn

import sqlite3

from fastapi import HTTPException, status


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