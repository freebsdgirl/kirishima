"""
This module provides an API endpoint for searching memory records via the ledger service.
It delegates memory search operations to the ledger microservice using HTTP API calls.
Supports searching by keywords, category, topic ID, memory ID, and time ranges.

Functions:
    memory_search_tool(keywords, category, topic_id, memory_id, min_keywords, created_after, created_before) -> dict:
        Tool function for searching memories via ledger service.
    memory_search(keywords: List[str], category: str, topic_id: str, memory_id: str, min_keywords: int) -> dict:
        FastAPI route handler for searching memories.
"""

import httpx
import json
import os
from typing import List, Optional

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

from fastapi import APIRouter, HTTPException, status, Query

router = APIRouter()


async def memory_search_tool(keywords=None, category=None, topic_id=None, memory_id=None, min_keywords=2, created_after=None, created_before=None):
    """
    Search for memories via the ledger service. Supports multiple search criteria that can be combined.
    
    Args:
        keywords (List[str], optional): List of keywords to search for.
        category (str, optional): Category to search for.
        topic_id (str, optional): The topic ID to search for.
        memory_id (str, optional): Memory ID to search for.
        min_keywords (int, optional): Minimum number of matching keywords required. Defaults to 2.
        created_after (str, optional): Return memories created after this timestamp (ISO format).
        created_before (str, optional): Return memories created before this timestamp (ISO format).
    Returns:
        dict: Status and list of matching memory records from ledger service.
    """
    logger.debug(f"memory_search_tool called with: keywords={keywords}, category={category}, topic_id={topic_id}, memory_id={memory_id}, min_keywords={min_keywords}, created_after={created_after}, created_before={created_before}")
    
    try:
        # Prepare search parameters
        search_params = {}
        if keywords is not None:
            search_params["keywords"] = keywords if isinstance(keywords, list) else [keywords]
        if category is not None:
            search_params["category"] = category
        if topic_id is not None:
            search_params["topic_id"] = topic_id
        if memory_id is not None:
            search_params["memory_id"] = memory_id
        if min_keywords is not None:
            search_params["min_keywords"] = int(min_keywords)
        if created_after is not None:
            search_params["created_after"] = created_after
        if created_before is not None:
            search_params["created_before"] = created_before

        # Call ledger service
        ledger_port = os.getenv("LEDGER_PORT", 4203)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(
                f'http://ledger:{ledger_port}/memories/_search',
                params=search_params
            )
            response.raise_for_status()
            return response.json()
            
    except httpx.TimeoutException:
        logger.error("Request to ledger service timed out")
        raise ValueError("Memory search request timed out")
    except httpx.RequestError as e:
        logger.error(f"Error calling ledger service: {e}")
        raise ValueError(f"Error searching memories: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in memory search: {e}")
        raise


@router.get("/memories/search", response_model=dict)
async def memory_search(
    keywords: List[str] = Query(None, description="List of keywords to search for."),
    category: str = Query(None, description="Category to search for."),
    topic_id: str = Query(None, description="The topic ID to search for."),
    memory_id: str = Query(None, description="Memory ID to search for."),
    min_keywords: int = Query(2, description="Minimum number of matching keywords required."),
    created_after: str = Query(None, description="Return memories created after this timestamp (ISO format)."),
    created_before: str = Query(None, description="Return memories created before this timestamp (ISO format).")
):
    """
    FastAPI endpoint for searching memories via ledger service. Supports multiple search criteria.
    Args:
        keywords (List[str], optional): List of keywords to search for.
        category (str, optional): Category to search for.
        topic_id (str, optional): The topic ID to search for.
        memory_id (str, optional): Memory ID to search for.
        min_keywords (int, optional): Minimum number of matching keywords required. Defaults to 2.
        created_after (str, optional): Return memories created after this timestamp (ISO format).
        created_before (str, optional): Return memories created before this timestamp (ISO format).
    Returns:
        dict: Status and list of matching memory records.
    """
    try:
        return await memory_search_tool(keywords, category, topic_id, memory_id, min_keywords, created_after, created_before)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {e}")