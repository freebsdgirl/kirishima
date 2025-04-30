"""
This module provides an API endpoint for deleting summaries from a ChromaDB collection.
It defines a FastAPI router with a DELETE endpoint at "/summary/{summary_id}" that allows clients to remove a summary by its unique ID. The endpoint utilizes dependency injection to access the ChromaDB collection and handles error cases where the summary does not exist, returning appropriate HTTP responses and logging errors.
Functions:
    delete_summary(summary_id: str, collection): Deletes a summary from the ChromaDB collection by its ID.
    HTTPException: Returns a 404 Not Found error if the summary ID does not exist in the collection.
"""

from app.summary.util import get_collection

from shared.log_config import get_logger
logger = get_logger(f"chromadb.{__name__}")

from fastapi import HTTPException, status, APIRouter, Depends
router = APIRouter()


@router.delete("/summary/{summary_id}")
def delete_summary(summary_id: str, collection = Depends(get_collection)):
    """
    Delete a summary from the ChromaDB collection.

    This endpoint handles deleting a summary by its ID. It removes the summary from the collection
    and returns a confirmation message.

    Args:
        summary_id (str): The ID of the summary to be deleted.
        collection: The ChromaDB collection to delete the summary from.
    Returns:
        dict: A message confirming successful deletion of the summary.
    Raises:
        HTTPException: If the summary ID is not found (404 Not Found).
    """
    try:
        # Attempt to delete the summary by its ID
        collection.delete(ids=[summary_id])
        return {"message": "Summary deleted successfully"}
    
    except Exception as e:
        # Log the error and raise a 404 if the summary ID is not found
        logger.error(f"Failed to delete summary with ID {summary_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Summary not found: {summary_id}"
        )