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

from shared.models.summary import Summary, SummaryMetadata, SummaryType

from fastapi import HTTPException, status, APIRouter, Depends
router = APIRouter()


@router.get("/summary", response_model=List[Summary])
async def get_summary(
    user_id: Optional[str] = None,
    type: Optional[SummaryType] = None,
    timestamp_begin: Optional[str] = None,
    timestamp_end: Optional[str] = None,
    limit: Optional[int] = None,
    collection = Depends(get_collection)
) -> List[Summary]:
    """
    Retrieve summaries based on optional filtering criteria.

    Fetches summaries from the collection matching specified user ID, summary type, 
    and timestamp range. Supports optional limit on number of returned summaries.

    Args:
        user_id (Optional[str]): Filter summaries by specific user ID.
        type (Optional[SummaryType]): Filter summaries by specific summary type.
        timestamp_begin (Optional[str]): Lower bound for summary timestamp.
        timestamp_end (Optional[str]): Upper bound for summary timestamp.
        limit (Optional[int], optional): Maximum number of summaries to return. Defaults to None.
        collection: ChromaDB collection for querying summaries.

    Returns:
        List[Summary]: Filtered and sorted list of summaries.

    Raises:
        HTTPException: 
            - 404 if no summaries match the given criteria
            - 500 for unexpected errors during retrieval
    """
    try:
        # Determine which field to use for the DB query
        db_field = None
        db_value = None
        if user_id:
            db_field = "user_id"
            db_value = user_id
        elif type:
            db_field = "summary_type"
            db_value = type

        where = {}
        if db_field and db_value:
            # If type is an Enum, use its value
            where[db_field] = {"$eq": db_value.value if hasattr(db_value, "value") else db_value}

        results = collection.get(where=where)

        if not results or not results.get("ids"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No summaries found for the given criteria"
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

        # Now filter in Python for the other fields
        if user_id and db_field != "user_id":
            summaries = [s for s in summaries if s.metadata.user_id == user_id]
        if type and db_field != "summary_type":
            summaries = [s for s in summaries if s.metadata.summary_type == type]
        if timestamp_begin:
            summaries = [s for s in summaries if s.metadata.timestamp_begin >= timestamp_begin]
        if timestamp_end:
            summaries = [s for s in summaries if s.metadata.timestamp_begin <= timestamp_end]

        summaries = sorted(
            summaries,
            key=lambda s: s.metadata.timestamp_begin
        )

        if limit:
            summaries = summaries[-limit:]

        return summaries

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Unexpected error in get_summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while retrieving summaries: {e}"
        )
