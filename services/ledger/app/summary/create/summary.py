"""
This module provides an API endpoint for generating ledger summaries based on specified periods.

It supports the following periods:
- "night", "morning", "afternoon", "evening" (periodic summaries)
- "daily", "weekly", "monthly" (aggregate summaries)

The main endpoint `/summary/create` accepts a `SummaryCreateRequest` containing one or more periods,
and returns a list of summary dictionaries. Each period is processed by its corresponding summary
creation function. If an invalid period is provided, an HTTP 400 error is raised.

Dependencies:
- FastAPI for API routing and exception handling
- Shared models and logging configuration
- Summary creation functions for each supported period
"""
from shared.models.ledger import SummaryCreateRequest, SummaryMetadata, Summary

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from fastapi import HTTPException, status, APIRouter
from typing import List
from app.summary.create.periodic import create_periodic_summary
from app.summary.create.daily import create_daily_summary
from app.summary.create.weekly import create_weekly_summary
from app.summary.create.monthly import create_monthly_summary

router = APIRouter()

VALID_PERIODS = ["night", "morning", "afternoon", "evening"]
ALL_PERIODS = VALID_PERIODS + ["daily", "weekly", "monthly"]

@router.post("/summary/create")
async def generate_summary(request: SummaryCreateRequest) -> List[dict]:
    # Accept period as List[str] (enforced in model)
    periods = request.period if isinstance(request.period, list) else [request.period]
    results = []
    for period in periods:
        if period in VALID_PERIODS:
            req = request.copy(update={"period": period})
            results.extend(await create_periodic_summary(req))
        elif period == "daily":
            req = request.copy(update={"period": period})
            results.extend(await create_daily_summary(req))
        elif period == "weekly":
            req = request.copy(update={"period": period})
            results.extend(await create_weekly_summary(req))
        elif period == "monthly":
            req = request.copy(update={"period": period})
            results.extend(await create_monthly_summary(req))
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid period: {period}"
            )
    return results
