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
from shared.models.ledger import UserSummary, UserSummaryList, DeleteSummary, DeleteRequest, CombinedSummaryRequest

import json

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
    if limit:
        query = f"SELECT * FROM (" + query + f" ORDER BY timestamp_begin DESC LIMIT ?) sub ORDER BY timestamp_begin ASC"
        params.append(limit)
    else:
        query += " ORDER BY timestamp_begin"

    with sqlite3.connect(BUFFER_DB, timeout=5.0, isolation_level=None) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
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

    with sqlite3.connect(BUFFER_DB, timeout=5.0, isolation_level=None) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
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
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            ledger_address, ledger_port = shared.consul.get_service_address('ledger')
            response = await client.get(f"http://{ledger_address}:{ledger_port}/ledger/user/{user_id}/messages")
            response.raise_for_status()
            buffer = response.json()
            if not buffer:
                return {"status": "ok", "detail": "empty buffer"}

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

    total_tokens = sum(len(tokenizer.encode(m["content"])) for m in buffer)
    if total_tokens < user_chunk_at:
        logger.info("Buffer < chunk_at (%s tokens), nothing to do", total_tokens)
        from fastapi import Response
        return Response(
            content=json.dumps({"status": "ok", "detail": "buffer below threshold"}),
            status_code=status.HTTP_200_OK,
            media_type="application/json"
        )

    # ------------ 2. Determine chunk ------------
    running_tokens = 0
    chunk: List[dict] = []
    for msg in buffer:
        chunk.append(msg)
        running_tokens += len(tokenizer.encode(msg["content"]))
        if running_tokens >= user_chunk_size:
            break
    summarized_at_id = chunk[-1]["id"]
    ts_begin = buffer[0]["created_at"]
    ts_end = chunk[-1]["created_at"]

    # ------------ 3. Summarize chunk ------------
    logger.debug(f"Summarizing {len(chunk)} messages")

    payload = {
        "messages": chunk,
        "max_tokens": user_summary_tokens
    }

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            brain_address, brain_port = shared.consul.get_service_address('brain')
        
            response = await client.post(
                f"http://{brain_address}:{brain_port}/summary/user", json=payload)
            print(f"Response: {response}")
            response.raise_for_status()
            if response.status_code != status.HTTP_201_CREATED:
                logger.error(f"Brain summary failed {response.status_code}: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Brain summarizer error"
                )
            if "summary" not in response.json():
                logger.error(f"Brain summary failed {response.status_code}: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Brain summarizer error"
                )
            summary_text = response.json()["summary"]

        except Exception as e:
            logger.exception(f"Error retrieving service address for brain: {e}")

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error forwarding from brain: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from brain: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error when contacting brain: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}"
            )

    # ------------ 4. DB write under lock ------------
    with sqlite3.connect(BUFFER_DB, timeout=5.0, isolation_level=None) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("BEGIN IMMEDIATE;")  # write lock until commit
        logger.debug(f"Inserting summary for user {user_id} at level 1")
        cur = conn.cursor()
        cur.execute(
            f"INSERT INTO {TABLE} (user_id, content, level, timestamp_begin, timestamp_end) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, summary_text, 1, ts_begin, ts_end),
        )
        conn.commit()

    # ------------ 5. Prune buffer ------------
    logger.debug(f"Deleting messages for user {user_id} up to message ID {summarized_at_id}")

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            ledger_address, ledger_port = shared.consul.get_service_address('ledger')
        
            response = await client.delete(
                f"http://{ledger_address}:{ledger_port}/ledger/user/{user_id}/before/{summarized_at_id}")
            response.raise_for_status()

        except Exception as e:
            logger.exception(f"Error retrieving service address for ledger: {e}")

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

    # ------------ 6. Cascade compression ------------
    with sqlite3.connect(BUFFER_DB, timeout=5.0, isolation_level=None) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        cur = conn.cursor()
        level = 1
        while level < MAX_LEVEL:
            # Count summaries at this level
            cur.execute(
                f"SELECT COUNT(*) FROM {TABLE} WHERE user_id = ? AND level = ?",
                (user_id, level)
            )
            summary_count = cur.fetchone()[0]
            if summary_count < user_summary_chunk_at:
                break

            # Select the 3 oldest summaries
            cur.execute(
                f"SELECT id, content, timestamp_begin, timestamp_end FROM {TABLE} "
                "WHERE user_id = ? AND level = ? ORDER BY id LIMIT ?",
                (user_id, level, user_summary_chunk_size),
            )
            rows = cur.fetchall()

            ids, contents, begins, ends = zip(*[(r[0], r[1], r[2], r[3]) for r in rows])

            logger.debug(f"Summarizing {len(list(contents))} summaries")

            from shared.models.ledger import UserSummary

            # Fetch the full UserSummary objects for the selected IDs
            cur.execute(
                f"SELECT * FROM {TABLE} WHERE id IN ({','.join(['?']*len(ids))})",
                ids,
            )
            columns = [col[0] for col in cur.description]
            user_summaries = [UserSummary(**dict(zip(columns, row))) for row in cur.fetchall()]

            payload = {
                "summaries": [s.model_dump() for s in user_summaries],
                "max_tokens": user_summary_tokens,
                # "user_alias": user_alias,  # add this if you have it available
            }

            async with httpx.AsyncClient(timeout=60) as client:
                try:
                    brain_address, brain_port = shared.consul.get_service_address('brain')
                
                    response = await client.post(
                        f"http://{brain_address}:{brain_port}/summary/user/combined", json=payload)
                    print(f"Response: {response}")
                    response.raise_for_status()
                    if response.status_code != status.HTTP_201_CREATED:
                        logger.error(f"Brain summary failed {response.status_code}: {response.text}")
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Brain summarizer error"
                        )
                    if "summary" not in response.json():
                        logger.error(f"Brain summary failed {response.status_code}: {response.text}")
                        raise HTTPException(
                            status_code=status.HTTP_502_BAD_GATEWAY,
                            detail="Brain summarizer error"
                        )
                    combined_summary = response.json()["summary"]

                except Exception as e:
                    logger.exception(f"Error retrieving service address for brain: {e}")

                except httpx.HTTPStatusError as http_err:
                    logger.error(f"HTTP error forwarding from brain: {http_err.response.status_code} - {http_err.response.text}")

                    raise HTTPException(
                        status_code=http_err.response.status_code,
                        detail=f"Error from brain: {http_err.response.text}"
                    )

                except httpx.RequestError as req_err:
                    logger.error(f"Request error when contacting brain: {req_err}")

                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Connection error: {req_err}"
                    )

            logger.debug(f"Inserting summary for user {user_id} at level {level+1}")
            cur2 = conn.cursor()
            cur2.execute(
                f"INSERT INTO {TABLE} (user_id, content, level, timestamp_begin, timestamp_end) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, combined_summary, level + 1, begins[0], ends[-1]),
            )
            cur.execute(
                f"DELETE FROM {TABLE} WHERE id IN ({','.join(['?']*len(ids))})",
                ids,
            )
            conn.commit()
            level += 1

    return {"status": "created"}
