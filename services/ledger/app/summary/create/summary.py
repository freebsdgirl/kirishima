"""
This module provides FastAPI endpoints and supporting functions for generating user conversation summaries
over various time periods (periodic, daily, weekly, monthly) in a chat application.
Key Features:
-------------
- Generates summaries for active users based on their chat messages, grouped by specified periods:
    - Periodic: "night", "morning", "afternoon", "evening"
    - Daily: Aggregates all period summaries for a day
    - Weekly: Aggregates daily summaries for a week (Monday-Sunday)
    - Monthly: Aggregates daily summaries for a month
- Utilizes external services for:
    - Fetching active users and their messages (ledger service)
    - Generating summaries via LLM API (proxy service)
    - Storing and retrieving summaries (ChromaDB)
- Handles chunking of messages to fit model token limits and combines multiple summaries when needed
- Provides robust error handling and logging for service communication and summary generation failures
Endpoints:
----------
- POST /summary: Accepts a summary creation request and generates summaries for the specified periods
Main Functions:
---------------
- generate_summary: Orchestrates summary generation for requested periods
- create_periodic_summary: Generates summaries for each active user for a specific period
- create_daily_summary: Aggregates period summaries into a daily summary per user
- create_weekly_summary: Aggregates daily summaries into a weekly summary per user
- create_monthly_summary: Aggregates daily summaries into a monthly summary per user
Dependencies:
-------------
- FastAPI, httpx, transformers, shared.models, shared.log_config, app.util
Environment Variables:
----------------------
- LEDGER_PORT, API_PORT, CHROMADB_PORT, PROXY_PORT
Configuration:
--------------
- Reads settings from /app/config/config.json (timeout, summary token limits, etc.)
"""
from shared.models.ledger import SummaryCreateRequest, SummaryMetadata, Summary

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from datetime import datetime, timedelta
from fastapi import HTTPException, status, APIRouter
from app.summary.post import _insert_summary
from app.summary.get import _get_summaries
from typing import List
import httpx
import json
import os
from shared.models.openai import OpenAICompletionRequest
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
