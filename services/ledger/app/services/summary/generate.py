from shared.models.ledger import SummaryCreateRequest

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from app.services.summary.create_periodic import _create_periodic_summary
from app.services.summary.create_daily import _create_daily_summary
from app.services.summary.create_weekly import _create_weekly_summary
from app.services.summary.create_monthly import _create_monthly_summary

from fastapi import HTTPException, status
from typing import List


VALID_PERIODS = ["night", "morning", "afternoon", "evening"]
ALL_PERIODS = VALID_PERIODS + ["daily", "weekly", "monthly"]

async def _generate_summary(request: SummaryCreateRequest) -> List[dict]:
    """
    Generate summaries based on the provided request.

    Args:
        request (SummaryCreateRequest): The request containing the periods and other parameters.

    Returns:
        List[dict]: A list of generated summaries.
    """
    if not isinstance(request.period, list):
        request.period = [request.period]

    results = []
    for period in request.period:
        if period in VALID_PERIODS:
            results.extend(await _create_periodic_summary(request.model_copy(update={"period": period})))
        elif period == "daily":
            results.extend(await _create_daily_summary(request.model_copy(update={"period": period})))
        elif period == "weekly":
            results.extend(await _create_weekly_summary(request.model_copy(update={"period": period})))
        elif period == "monthly":
            results.extend(await _create_monthly_summary(request.model_copy(update={"period": period})))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid period: {period}"
            )
    return results