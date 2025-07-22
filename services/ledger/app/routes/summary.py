from app.services.summary.delete import _delete_summary

from shared.models.ledger import DeleteSummary, SummaryDeleteRequest

from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

from typing import Optional
from fastapi import APIRouter, Query
router = APIRouter()


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