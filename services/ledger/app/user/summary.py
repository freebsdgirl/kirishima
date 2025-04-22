"""
This module provides FastAPI endpoints and helper functions for managing user message summaries
in a ledger system. It supports chunked summarization of user message buffers, cascade compression
of summaries into higher-level summaries, and CRUD operations on user summaries stored in a SQLite
database. Summarization is performed via a proxy service, and message buffers are fetched and pruned
via HTTP requests to a ledger service.
Key Features:
- Fetch and summarize user message buffers when they exceed a token threshold.
- Store summaries at multiple hierarchical levels, with automatic cascade compression.
- List and delete user summaries with optional filtering.
- Integrate with external services for message retrieval and summarization.
- Use SQLite with Write-Ahead Logging for concurrent access.
Endpoints:
- GET /summaries/user/{user_id}: List summaries for a user.
- DELETE /summaries/user/{user_id}: Delete specific summaries for a user.
- POST /summaries/user/{user_id}/create: Summarize user buffer and perform cascade compression.
Helper Functions:
- Database connection and summary insertion.
- Token counting using GPT-2 tokenizer.
- HTTP requests to ledger and proxy summarization services.
"""

from app.config import (
    BUFFER_DB,
    user_chunk_size,
    user_chunk_at,
    user_summary_chunk_size,
    user_summary_chunk_at,
    user_summary_tokens,
)

import shared.consul
from shared.models.ledger import UserSummary, UserSummaryList, DeleteSummary, DeleteRequest

from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

from typing import List, Optional

import httpx
import tiktoken
import sqlite3

from fastapi import APIRouter, Path, Query, Body, HTTPException, status
router = APIRouter()

TABLE = "user_summaries"
MAX_LEVEL = 10

tokenizer = tiktoken.get_encoding("gpt2")


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


def _count_tokens(text: str) -> int:
    """
    Count the number of tokens in a given text using the GPT-2 tokenizer.
    
    Args:
        text (str): The input text to tokenize.
    
    Returns:
        int: The number of tokens in the input text.
    """
    return len(tokenizer.encode(text))


async def _fetch_user_buffer(user_id: str) -> List[dict]:
    """
    Fetch all messages for a given user from the ledger service.
    
    Args:
        user_id (str): The unique identifier of the user whose messages are to be retrieved.
    
    Returns:
        List[dict]: A list of message dictionaries for the specified user.
    
    Raises:
        HTTPException: If the request to the ledger service fails.
    """

    logger.debug(f"Fetching messages for user {user_id}")

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            ledger_address, ledger_port = shared.consul.get_service_address('ledger')
        
            response = await client.get(
                f"http://{ledger_address}:{ledger_port}/ledger/user/{user_id}/messages")
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


async def _delete_user_buffer_to(user_id: str, message_id: int) -> None:
    """
    Delete messages from a user's buffer up to a specific message ID.
    
    Args:
        user_id (str): The unique identifier of the user whose messages will be deleted.
        message_id (int): The ID of the message up to which all previous messages will be deleted.
    
    Raises:
        HTTPException: If the request to the ledger service fails.
    """

    logger.debug(f"Deleting messages for user {user_id} up to message ID {message_id}")

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            ledger_address, ledger_port = shared.consul.get_service_address('ledger')
        
            response = await client.delete(
                f"http://{ledger_address}:{ledger_port}/ledger/user/{user_id}/before/{message_id}")
            response.raise_for_status()

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


async def _proxy_summary(messages: List[dict], max_tokens: int) -> str:
    """
    Send messages to a proxy summarization service and retrieve a summary.
    
    Args:
        messages (List[dict]): A list of message dictionaries to be summarized.
        max_tokens (int): The maximum number of tokens allowed in the summary.
    
    Returns:
        str: A summarized text of the input messages.
    
    Raises:
        HTTPException: If the proxy summarization service fails to generate a summary.
    """

    logger.debug(f"Summarizing {len(messages)} messages")

    payload = {"messages": messages, "max_tokens": max_tokens}

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            proxy_address, proxy_port = shared.consul.get_service_address('proxy')
        
            response = await client.post(
                f"http://{proxy_address}:{proxy_port}/summary/user", json=payload)
            response.raise_for_status()
            if response.status_code != status.HTTP_201_CREATED:
                logger.error("Proxy summary failed %s: %s", response.status_code, response.text)
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


async def _proxy_summary_of_summaries(summaries: List[str], max_tokens: int) -> str:
    """
    Send a list of summaries to a proxy summarization service and retrieve a consolidated summary.
    
    Args:
        summaries (List[str]): A list of summary texts to be consolidated.
        max_tokens (int): The maximum number of tokens allowed in the final summary.
    
    Returns:
        str: A summarized text of the input summaries.
    
    Raises:
        HTTPException: If the proxy summarization service fails to generate a summary.
    """
    logger.debug(f"Summarizing {len(summaries)} summaries")

    payload = {"summaries": summaries, "max_tokens": max_tokens}

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            proxy_address, proxy_port = shared.consul.get_service_address('proxy')
        
            response = await client.post(
                f"http://{proxy_address}:{proxy_port}/summary/user/summary", json=payload)
            response.raise_for_status()
            if response.status_code != status.HTTP_201_CREATED:
                logger.error("Proxy summary failed %s: %s", response.status_code, response.text)
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


def _insert_summary(conn: sqlite3.Connection, user_id: str, content: str, level: int,
                    ts_begin: str, ts_end: str) -> None:
    """
    Insert a new summary record into the database for a specific user.
    
    Args:
        conn (sqlite3.Connection): The database connection.
        user_id (str): The identifier of the user.
        content (str): The summary content to be inserted.
        level (int): The level or hierarchy of the summary.
        ts_begin (str): The beginning timestamp of the summary.
        ts_end (str): The ending timestamp of the summary.
    """
    logger.debug(f"Inserting summary for user {user_id} at level {level}")

    cur = conn.cursor()
    cur.execute(
        f"INSERT INTO {TABLE} (user_id, content, level, timestamp_begin, timestamp_end) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, content, level, ts_begin, ts_end),
    )


@router.get("/summaries/user/{user_id}", response_model=UserSummaryList)
async def list_summaries(
    user_id: str = Path(...),
    limit: Optional[int] = Query(None, ge=1),
    level: Optional[int] = Query(None, ge=1),
):
    """
    Retrieve a list of user summaries with optional filtering and pagination.

    Args:
        user_id (str): The unique identifier of the user whose summaries are being retrieved.
        limit (Optional[int], optional): Maximum number of summaries to return. Defaults to None.
        level (Optional[int], optional): Filter summaries by a specific hierarchical level. Defaults to None.

    Returns:
        UserSummaryList: A list of user summaries matching the specified criteria.

    Endpoint: GET /summaries/user/{user_id}
    """
    logger.debug(f"Fetching summaries for user {user_id} with limit {limit} and level {level}")

    query = f"SELECT * FROM {TABLE} WHERE user_id = ?"
    params: List = [user_id]
    if level is not None:
        query += " AND level = ?"
        params.append(level)
    query += " ORDER BY id"
    if limit:
        query += " LIMIT ?"
        params.append(limit)

    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute(query, tuple(params))
        columns = [col[0] for col in cur.description]
        rows = cur.fetchall()
        return UserSummaryList(summaries=[UserSummary(**dict(zip(columns, row))) for row in rows])


@router.delete("/summaries/user/{user_id}", response_model=DeleteSummary)
async def delete_summaries(
    user_id: str = Path(...),
    body: DeleteRequest = Body(...),
):
    """
    Delete specific user summaries by their IDs.

    Endpoint: DELETE /summaries/user/{user_id}
    Deletes a set of summaries for a given user based on provided summary IDs.

    Args:
        user_id (str): The unique identifier of the user whose summaries will be deleted.
        body (DeleteRequest): A request body containing the list of summary IDs to delete.

    Returns:
        DeleteSummary: An object indicating the number of summaries successfully deleted.
    """
    logger.debug(f"Deleting summaries for user {user_id} with IDs {body.ids}")

    with _open_conn() as conn:
        cur = conn.cursor()
        q_marks = ",".join(["?"] * len(body.ids))
        cur.execute(
            f"DELETE FROM {TABLE} WHERE user_id = ? AND id IN ({q_marks})",
            (user_id, *body.ids),
        )
        deleted = cur.rowcount
        conn.commit()
        return DeleteSummary(deleted=deleted)


@router.post("/summaries/user/{user_id}/create", status_code=status.HTTP_201_CREATED)
async def create_summaries(user_id: str = Path(...)):
    """
    Creates a summary for a user's message buffer if it exceeds a specified token threshold, and performs cascade compression of summaries.

    Workflow:
    1. Fetches the user's message buffer.
    2. If the buffer is empty or below the token threshold, returns early.
    3. Determines the oldest chunk of messages that exceeds the chunk size.
    4. Summarizes the chunk using a proxy summarization function.
    5. Writes the summary to the database under a write lock.
    6. Prunes the summarized messages from the buffer.
    7. Performs cascade compression: repeatedly combines and summarizes lower-level summaries into higher-level summaries if enough exist.

    Args:
        user_id (str): The ID of the user whose buffer is to be summarized.

    Returns:
        dict: A status message indicating the result of the operation.
    """
    logger.debug(f"Creating summaries for user {user_id}")

    # ------------ 1. Fetch buffer ------------
    buffer = await _fetch_user_buffer(user_id)
    if not buffer:
        return {"status": "ok", "detail": "empty buffer"}

    total_tokens = sum(_count_tokens(m["content"]) for m in buffer)
    if total_tokens < user_chunk_at:
        logger.info("Buffer < chunk_at (%s tokens), nothing to do", total_tokens)
        return {"status": "ok", "detail": "buffer below threshold"}

    # ------------ 2. Determine chunk ------------
    running_tokens = 0
    chunk: List[dict] = []
    for msg in buffer:
        chunk.append(msg)
        running_tokens += _count_tokens(msg["content"])
        if running_tokens >= user_chunk_size:
            break
    summarized_at_id = chunk[-1]["id"]
    ts_begin = buffer[0]["created_at"]
    ts_end = chunk[-1]["created_at"]

    # ------------ 3. Summarize chunk ------------
    summary_text = await _proxy_summary(chunk, user_summary_tokens)

    # ------------ 4. DB write under lock ------------
    with _open_conn() as conn:
        conn.execute("BEGIN IMMEDIATE;")  # write lock until commit
        _insert_summary(conn, user_id, summary_text, 1, ts_begin, ts_end)
        conn.commit()

    # ------------ 5. Prune buffer ------------
    await _delete_user_buffer_to(user_id, summarized_at_id)

    # ------------ 6. Cascade compression ------------
    with _open_conn() as conn:
        cur = conn.cursor()
        level = 1
        while level < MAX_LEVEL:
            cur.execute(
                f"SELECT id, content, timestamp_begin, timestamp_end FROM {TABLE} "
                "WHERE user_id = ? AND level = ? ORDER BY id LIMIT ?",
                (user_id, level, user_summary_chunk_size),
            )
            rows = cur.fetchall()
            if len(rows) < user_summary_chunk_at:
                break

            ids, contents, begins, ends = zip(*[(r[0], r[1], r[2], r[3]) for r in rows])
            combined_summary = await _proxy_summary_of_summaries(list(contents), user_summary_tokens)
            _insert_summary(
                conn,
                user_id,
                combined_summary,
                level + 1,
                begins[0],  # oldest begin
                ends[-1],   # newest end
            )
            cur.execute(
                f"DELETE FROM {TABLE} WHERE id IN ({','.join(['?']*len(ids))})",
                ids,
            )
            conn.commit()
            level += 1

    return {"status": "created"}
