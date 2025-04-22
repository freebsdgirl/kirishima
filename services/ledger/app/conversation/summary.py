"""
This module provides FastAPI endpoints and helper functions for managing conversation summaries
(daily, weekly, monthly) in a ledger application. It interacts with both a local SQLite buffer
and remote services for message retrieval and summarization.

Key functionalities:
- Fetching conversation messages from a remote ledger service.
- Creating daily summaries from conversation messages within a 24-hour window.
- Combining daily summaries into weekly, and weekly into monthly summaries.
- Storing and retrieving summaries in/from a local SQLite database.
- Pruning old conversation messages from the buffer, retaining a configurable tail.
- Proxying summarization requests to an external summarizer service.
- Exposing endpoints for listing, creating, and managing conversation summaries.

Dependencies:
- FastAPI for API routing and request handling.
- httpx for asynchronous HTTP requests.
- sqlite3 for local buffer storage.
- Shared models and configuration for consistent data handling and logging.
"""
from app.config import (
    BUFFER_DB,
    conversation_buffer_keep,
)
from shared.models.ledger import (
    ConversationSummary,
    ConversationSummaryList
)

import shared.consul

from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx
import sqlite3
import asyncio

from fastapi import APIRouter, Path, Query, HTTPException, status
router = APIRouter()

TABLE = "conversation_summaries"


def _open_conn() -> sqlite3.Connection:
    """
    Open a SQLite database connection with Write-Ahead Logging (WAL) mode.

    Creates a connection to the BUFFER_DB with a 5-second timeout and WAL journal mode,
    which allows for better concurrency and performance in write-heavy scenarios.

    Returns:
        sqlite3.Connection: An open database connection configured with WAL mode.
    """
    conn = sqlite3.connect(BUFFER_DB, timeout=5.0, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


async def _fetch_conversation_buffer(conv_id: str) -> List[dict]:
    """
    Fetch messages for a specific conversation from the ledger service.

    Retrieves all messages for a given conversation ID by making an asynchronous HTTP GET request
    to the ledger service with a 60-second timeout.

    Args:
        conv_id (str): The unique identifier of the conversation.

    Returns:
        List[dict]: A list of message dictionaries from the conversation buffer.

    Raises:
        HTTPException: If the request to the ledger service fails.
    """
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            ledger_address, ledger_port = shared.consul.get_service_address('ledger')
        
            response = await client.get(
                f"http://{ledger_address}:{ledger_port}/ledger/conversation/{conv_id}/messages")
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.exception("Error retrieving service address for ledger:", e)

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error forwarding from ledger: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from ledger: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error when contacting ledger: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}"
            )



async def _delete_conversation_buffer_before(conv_id: str, timestamp_cut: str) -> None:
    """
    Delete messages from a conversation buffer that are older than a specified timestamp.

    Fetches messages for a given conversation, and removes messages older than timestamp_cut,
    while preserving the most recent messages defined by conversation_buffer_keep.

    Args:
        conv_id (str): The unique identifier of the conversation.
        timestamp_cut (str): The cutoff timestamp for message deletion.

    Note:
        This is an internal method that sequentially deletes messages from the conversation buffer
        via the ledger service endpoint.
    """
    messages = await _fetch_conversation_buffer(conv_id)
    if len(messages) <= conversation_buffer_keep:
        return  # nothing to prune
    # messages ordered by id ASC from buffer endpoint
    to_consider = messages[: -conversation_buffer_keep]
    ids_to_delete = [m["id"] for m in to_consider if m["created_at"] < timestamp_cut]
    if not ids_to_delete:
        return
    async with httpx.AsyncClient(timeout=60) as client:
        q_marks = ",".join(["?"] * len(ids_to_delete))
        # Internal delete – we expose an endpoint that accepts list? we don’t have one yet; quick loop:
        for chunk_id in ids_to_delete:
            try:
                ledger_address, ledger_port = shared.consul.get_service_address('brain')

                await client.delete(f"http://{ledger_address}:{ledger_port}/ledger/conversation/{conv_id}/before/{chunk_id}")

            except Exception as e:
                logger.exception("Error retrieving service address for ledger:", e)

            except httpx.HTTPStatusError as http_err:
                logger.error(f"HTTP error forwarding from ledger: {http_err.response.status_code} - {http_err.response.text}")

                raise HTTPException(
                    status_code=http_err.response.status_code,
                    detail=f"Error from ledger: {http_err.response.text}"
                )

            except httpx.RequestError as req_err:
                logger.error(f"Request error when contacting ledger: {req_err}")

                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Connection error: {req_err}"
                )


async def _proxy_conv_summary(period: str, messages_or_summaries: List[str]) -> str:
    """
    Proxy a conversation summary request to an external summarization service.

    Sends messages or existing summaries to a proxy endpoint for generating
    a summary based on the specified time period (daily, weekly, or monthly).

    Args:
        period (str): The summarization period ('daily', 'weekly', or 'monthly').
        messages_or_summaries (List[str]): List of messages or existing summaries to summarize.

    Returns:
        str: The generated summary from the proxy service.

    Raises:
        HTTPException: If the proxy summarization request fails.
    """
    endpoint = {
        "daily": "conversation/daily",
        "weekly": "conversation/weekly",
        "monthly": "conversation/monthly",
    }[period]
    payload = {
        "messages" if period == "daily" else "summaries": messages_or_summaries,
    }
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            proxy_address, proxy_port = shared.consul.get_service_address('proxy')
        
            response = await client.post(
                f"http://{proxy_address}:{proxy_port}/summary/{endpoint}", json=payload)
            response.raise_for_status()
            if response.status_code != status.HTTP_201_CREATED:
                logger.error("Proxy %s summary failed %s: %s", period, response.status_code, response.text)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Proxy summariser error"
                )
            return response.json()["summary"]

        except Exception as e:
            logger.exception("Error retrieving service address for ledger:", e)

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error forwarding from ledger: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from ledger: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error when contacting ledger: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}"
            )


def _insert_conv_summary(
    conn: sqlite3.Connection,
    conv_id: str,
    content: str,
    period: str,
    ts_begin: str,
    ts_end: str,
) -> None:
    """
    Insert a conversation summary into the database.
    
    Args:
        conn (sqlite3.Connection): Database connection.
        conv_id (str): Conversation identifier.
        content (str): Summary content text.
        period (str): Summary period (e.g., 'daily', 'weekly', 'monthly').
        ts_begin (str): Start timestamp of the summary period.
        ts_end (str): End timestamp of the summary period.
    """
    cur = conn.cursor()
    cur.execute(
        f"INSERT INTO {TABLE} (conversation_id, content, period, timestamp_begin, timestamp_end) "
        "VALUES (?, ?, ?, ?, ?)",
        (conv_id, content, period, ts_begin, ts_end),
    )


@router.get("/summaries/conversation/{conversation_id}", response_model=ConversationSummaryList)
async def list_conv_summaries(
    conversation_id: str = Path(...),
    period: Optional[str] = Query(None, regex="^(daily|weekly|monthly)$"),
    limit: Optional[int] = Query(None, ge=1),
):
    """
    Retrieve conversation summaries for a specific conversation.

    Allows filtering by summary period (daily/weekly/monthly) and limiting the number of results.

    Args:
        conversation_id (str): Unique identifier of the conversation.
        period (Optional[str], optional): Filter summaries by period type. Defaults to None.
        limit (Optional[int], optional): Maximum number of summaries to return. Defaults to None.

    Returns:
        ConversationSummaryList: A list of conversation summaries matching the query parameters.
    """

    query = f"SELECT * FROM {TABLE} WHERE conversation_id = ?"
    params: List = [conversation_id]
    if period:
        query += " AND period = ?"
        params.append(period)
    query += " ORDER BY id"
    if limit:
        query += " LIMIT ?"
        params.append(limit)
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        return ConversationSummaryList(
            summaries=[ConversationSummary(*row) for row in rows]
        )


@router.post("/summaries/conversation/{conversation_id}/daily/create", status_code=201)
async def create_daily_summary(conversation_id: str = Path(...)):
    """
    Create a daily summary for a specific conversation.

    Generates a summary of conversation messages from the 48-24 hour window before the current time.
    Stores the summary in the database and prunes older messages from the conversation buffer.

    Args:
        conversation_id (str): Unique identifier of the conversation to summarize.

    Returns:
        dict: Status of summary creation, with either "created" or "ok" status.
    """

    now = datetime.now()
    end_window = now - timedelta(hours=24)
    start_window = now - timedelta(hours=48)

    messages = await _fetch_conversation_buffer(conversation_id)
    # Filter window 48‑24 h ago
    window_msgs = [
        m for m in messages
        if start_window.isoformat() <= m["created_at"] < end_window.isoformat()
    ]
    if not window_msgs:
        return {"status": "ok", "detail": "nothing to summarise"}

    summary_text = await _proxy_conv_summary("daily", window_msgs)

    with _open_conn() as conn:
        conn.execute("BEGIN IMMEDIATE;")
        _insert_conv_summary(
            conn,
            conversation_id,
            summary_text,
            "daily",
            window_msgs[0]["created_at"],
            window_msgs[-1]["created_at"],
        )
        conn.commit()

    # prune messages older than 24h (excluding keep‑tail)
    await _delete_conversation_buffer_before(conversation_id, end_window.isoformat())

    return {"status": "created"}


def _combine_and_store(conv_id: str, period_from: str, period_to: str, days: int):
    """
    Combine summaries from a specific period into a larger aggregated summary.
    
    Retrieves summaries from the previous period within a specified time window,
    combines their contents, and stores the new summary in the database.
    
    Args:
        conv_id (str): Conversation identifier.
        period_from (str): Source summary period type (e.g., 'daily').
        period_to (str): Target summary period type (e.g., 'weekly').
        days (int): Number of days to look back for source summaries.
    
    Returns:
        bool: True if summaries were combined and stored successfully, False if no summaries found.
    """
    now = datetime.now()
    end_window = now - timedelta(days=days)
    start_window = end_window - timedelta(days=days)
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, content, timestamp_begin, timestamp_end FROM {TABLE} "
            "WHERE conversation_id = ? AND period = ? AND timestamp_summarized >= ? AND timestamp_summarized < ?"
            "ORDER BY id",
            (conv_id, period_from, start_window.isoformat(), end_window.isoformat()),
        )
        rows = cur.fetchall()
        if len(rows) == 0:
            return False
        contents = [r[1] for r in rows]
        combined = asyncio.run(_proxy_conv_summary(period_to, contents))  # sync helper
        _insert_conv_summary(
            conn,
            conv_id,
            combined,
            period_to,
            rows[0][2],
            rows[-1][3],
        )
        conn.commit()
        return True

@router.post("/summaries/conversation/{conversation_id}/weekly/create", status_code=201)
async def create_weekly_summary(conversation_id: str = Path(...)):
    """
    Create a weekly summary for a given conversation by combining daily summaries.

    Endpoint to generate a weekly summary by aggregating daily summaries from the past 7 days.
    Returns a status indicating whether the summary was successfully created.

    Args:
        conversation_id (str): The unique identifier of the conversation to summarize.

    Returns:
        dict: A status response with 'created' or 'ok' status and a detail message.
    """

    ok = _combine_and_store(conversation_id, "daily", "weekly", 7)
    return {"status": "created" if ok else "ok", "detail": "weekly summariser"}


@router.post("/summaries/conversation/{conversation_id}/monthly/create", status_code=201)
async def create_monthly_summary(conversation_id: str = Path(...)):
    ok = _combine_and_store(conversation_id, "weekly", "monthly", 30)
    return {"status": "created" if ok else "ok", "detail": "monthly summariser"}
