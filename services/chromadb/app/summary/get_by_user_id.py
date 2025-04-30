"""
Endpoint to retrieve summaries for a given user ID.

This endpoint fetches all summaries associated with the specified user ID from the collection.
Optionally, a limit can be set to restrict the number of returned summaries.
Summaries are sorted by their `timestamp_begin` metadata field.

Args:
    user_id (str): The ID of the user whose summaries are to be retrieved.
    limit (Optional[int], optional): The maximum number of summaries to return. Defaults to None (no limit).
    collection: The database collection dependency, injected by FastAPI.

Returns:
    List[Summary]: A list of Summary objects for the given user, sorted by `timestamp_begin`.

Raises:
    HTTPException: 
        - 404 if no summaries are found for the given user ID.
        - 500 for any unexpected errors during retrieval.
"""

from app.summary.util import get_collection

from typing import Optional, List

from shared.log_config import get_logger
logger = get_logger(f"chromadb.{__name__}")

from shared.models.summary import Summary, SummaryMetadata

from fastapi import HTTPException, status, APIRouter, Depends
router = APIRouter()


@router.get("/summary/{user_id}", response_model=List[Summary])
async def get_summary_by_user_id(user_id: str, limit: Optional[int] = None, collection = Depends(get_collection)) -> List[Summary]:
    """
    Retrieve summaries for a specific user with optional result limiting.

    Fetches summaries from the collection filtered by user ID, sorted by timestamp.
    Supports optional limit on number of returned summaries.

    Args:
        user_id (str): The unique identifier of the user whose summaries are to be retrieved.
        limit (Optional[int], optional): Maximum number of summaries to return. Defaults to None.
        collection: ChromaDB collection dependency for querying summaries.

    Returns:
        List[Summary]: Sorted list of summaries for the specified user.

    Raises:
        HTTPException:
            - 404 if no summaries are found for the given user ID
            - 500 for unexpected errors during summary retrieval
    """
    try:
        results = collection.get(
            where={
                "user_id": {"$eq": user_id}
            }
        )

        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No summaries found for the given user ID"
            )

        summaries = []
        for i in range(len(results["ids"])):
            summary = Summary(
                id=results["ids"][i],
                content=results["documents"][i],
                metadata=SummaryMetadata(
                    user_id=results["metadatas"][i].get("user_id"),
                    summary_type=results["metadatas"][i].get("summary_type"),
                    timestamp_begin=results["metadatas"][i].get("timestamp_begin"),
                    timestamp_end=results["metadatas"][i].get("timestamp_end"),
                )
            )
            summaries.append(summary)

        summaries = sorted(
            summaries,
            key=lambda s: s.metadata.timestamp_begin
        )

        if limit:
            summaries = summaries[:limit]

        return summaries

    except HTTPException:
        raise  # Let FastAPI handle HTTPExceptions as usual

    except Exception as e:
        logger.error(f"Unexpected error in get_summary_by_type: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while retrieving summaries: {e}"
        )
