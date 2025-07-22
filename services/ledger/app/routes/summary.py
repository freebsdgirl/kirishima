"""
This module defines FastAPI routes for managing summary records in the ledger service.
Routes:
    - GET /: Retrieve summaries based on optional filtering criteria such as ID, period, timestamp range, keywords, and limit.
    - DELETE /: Delete summaries filtered by ID, period, and timestamp range.
    - POST /: Create a new summary record in the SQLite ledger database.
    - POST /create: Generate summaries based on the provided summary creation request.
Dependencies:
    - app.services.summary.delete: Summary deletion logic.
    - app.services.summary.get: Summary retrieval logic.
    - app.services.summary.insert: Summary insertion logic.
    - app.services.summary.generate: Summary generation logic.
    - shared.models.ledger: Data models for summary operations.
    - shared.log_config: Logger configuration.
All endpoints handle exceptions and log errors appropriately.
"""

from app.services.summary.delete import _delete_summary
from app.services.summary.get import _get_summaries
from app.services.summary.insert import _insert_summary
from app.services.summary.generate import _generate_summary

from shared.models.ledger import (
    DeleteSummary,
    SummaryDeleteRequest,
    Summary,
    SummaryGetRequest,
    SummaryCreateRequest
)

from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

from typing import Optional, List

from fastapi import APIRouter, Query, HTTPException, status, Body

router = APIRouter()


@router.get("", response_model=List[Summary])
def get_summary(
    id: Optional[str] = Query(None, description="Filter by summary ID."),
    period: Optional[str] = Query(None, description="Filter summaries by summary period ('morning', 'afternoon', 'daily', etc)."),
    timestamp_begin: Optional[str] = Query(None, description="Lower bound for summary timestamp (YYYY-MM-DD HH:MM:SS)."),
    timestamp_end: Optional[str] = Query(None, description="Upper bound for summary timestamp (YYYY-MM-DD HH:MM:SS)."),
    keywords: Optional[List[str]] = Query(None, description="List of keywords to search for in summary text."),
    limit: Optional[int] = Query(None, description="Maximum number of summaries to return."),
) -> List[Summary]:
    """
    Retrieve summaries based on optional filtering criteria.
    """
    request = SummaryGetRequest(
        id=id,
        period=period,
        timestamp_begin=timestamp_begin,
        timestamp_end=timestamp_end,
        keywords=keywords,
        limit=limit
    )
    try:
        summaries = _get_summaries(request)
        if not summaries:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No summaries found for the given criteria"
            )
        return summaries
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while retrieving summaries: {e}"
        )


@router.delete("", response_model=DeleteSummary)
def delete_summary(
    id: Optional[str] = Query(None, description="ID of the summary to delete."),
    period: Optional[str] = Query(None, description="Time period (e.g., 'morning', 'afternoon', 'daily', etc.)"),
    timestamp_begin: Optional[str] = Query(None, description="Lower bound for deletion timestamp range"),
    timestamp_end: Optional[str] = Query(None, description="Upper bound for deletion timestamp range"),
) -> DeleteSummary:
    """
    Delete summary filtered by ID or period and date.
    """
    request = SummaryDeleteRequest(
        id=id,
        period=period,
        timestamp_begin=timestamp_begin,
        timestamp_end=timestamp_end
    )
    deleted_count = _delete_summary(request)
    return DeleteSummary(deleted=deleted_count)


@router.post("", response_model=Summary)
def create_summary(
    summary: Summary = Body(..., description="Summary object to insert")
) -> Summary:
    """
    Create a new summary record in the SQLite ledger database.
    """
    try:
        return _insert_summary(summary)
    except Exception as e:
        logger.error(f"Error creating summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create summary: {e}"
        )


@router.post("/create")
async def generate_summary(request: SummaryCreateRequest) -> List[dict]:
    """
    Generate a summary based on the provided summary create request.
    
    Args:
        request (SummaryCreateRequest): The request containing parameters for summary generation.
    
    Returns:
        List[dict]: A list of generated summary dictionaries.
    """
    return await _generate_summary(request)
