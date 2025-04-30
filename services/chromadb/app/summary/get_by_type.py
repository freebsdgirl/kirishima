"""
This module provides an API endpoint for retrieving summaries by user ID and summary type.

Functions:
    get_summary_by_type(user_id: str, summary_type: SummaryType, limit: Optional[int] = None, collection = Depends(get_collection)):
        Asynchronous FastAPI route handler that retrieves a list of summaries for a specific user and summary type from a ChromaDB collection.
        The results are sorted by the summary's starting timestamp and can be optionally limited in number.
        Returns a list of Summary objects or raises an HTTPException if no summaries are found or an unexpected error occurs.
"""

from app.summary.util import get_collection

from typing import Optional, List

from shared.log_config import get_logger
logger = get_logger(f"chromadb.{__name__}")

from shared.models.summary import Summary, SummaryMetadata, SummaryType

from fastapi import HTTPException, status, APIRouter, Depends
router = APIRouter()


@router.get("/summary/{user_id}/{summary_type}", response_model=List[Summary])
async def get_summary_by_type(user_id: str, summary_type: SummaryType, limit: Optional[int] = None, collection = Depends(get_collection)) -> List[Summary]:
    """
    Retrieve summaries for a specific user and summary type.

    Args:
        user_id (str): The unique identifier of the user.
        summary_type (SummaryType): The type of summary to retrieve.
        limit (Optional[int], optional): Maximum number of summaries to return. Defaults to None.
        collection: ChromaDB collection dependency for querying summaries.

    Returns:
        List[Summary]: A list of summaries sorted by timestamp, optionally limited.

    Raises:
        HTTPException: 404 error if no summaries are found for the given user ID and summary type.
    """
    try:
        results = collection.get(
            where={
                "$and": [
                    {"user_id": {"$eq": user_id}},
                    {"summary_type": {"$eq": summary_type}},
                ]
            }
        )

        if not results:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No summaries found for the given user ID and summary type"
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
