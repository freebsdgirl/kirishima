"""summary_service.py — Summarization pipeline endpoints (lives in ledger for now).

Variables from app.config:
    user_chunk_size         = 512
    user_chunk_at           = 1024
    user_summary_chunk_size = 3
    user_summary_chunk_at   = 5
    user_summary_tokens     = 128
"""

from typing import List, Optional

import httpx
import tiktoken
import sqlite3

from fastapi import APIRouter, Path, Query, Body, HTTPException, status
from shared.log_config import get_logger
from shared.models.ledger import UserSummary, UserSummaryList, DeleteSummary, DeleteRequest
from app.config import (
    BUFFER_DB,
    user_chunk_size,
    user_chunk_at,
    user_summary_chunk_size,
    user_summary_chunk_at,
    user_summary_tokens,
)

logger = get_logger(__name__)
router = APIRouter()

TABLE = "user_summaries"
LEDGER_URL = "http://ledger:4200"  # assuming self host; change if needed
PROXY_URL = "http://proxy:4205"
MAX_LEVEL = 10

tokenizer = tiktoken.get_encoding("gpt2")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _open_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(BUFFER_DB, timeout=5.0, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def _count_tokens(text: str) -> int:
    return len(tokenizer.encode(text))

async def _fetch_user_buffer(user_id: str) -> List[dict]:
    async with httpx.AsyncClient() as cli:
        r = await cli.get(f"{LEDGER_URL}/ledger/user/{user_id}/messages", timeout=30)
        r.raise_for_status()
        return r.json()

async def _delete_user_buffer_to(user_id: str, message_id: int) -> None:
    async with httpx.AsyncClient() as cli:
        r = await cli.delete(
            f"{LEDGER_URL}/ledger/user/{user_id}/before/{message_id}", timeout=30
        )
        r.raise_for_status()

async def _proxy_summary(messages: List[dict], max_tokens: int) -> str:
    payload = {"messages": messages, "max_tokens": max_tokens}
    async with httpx.AsyncClient() as cli:
        r = await cli.post(f"{PROXY_URL}/summary/user", json=payload, timeout=60)
        if r.status_code != status.HTTP_201_CREATED:
            logger.error("Proxy summary failed %s: %s", r.status_code, r.text)
            raise HTTPException(status_code=502, detail="Proxy summarizer error")
        return r.json()["summary"]

async def _proxy_summary_of_summaries(summaries: List[str], max_tokens: int) -> str:
    payload = {"summaries": summaries, "max_tokens": max_tokens}
    async with httpx.AsyncClient() as cli:
        r = await cli.post(f"{PROXY_URL}/summary/user/summary", json=payload, timeout=60)
        if r.status_code != status.HTTP_201_CREATED:
            logger.error("Proxy summary-of-summaries failed %s: %s", r.status_code, r.text)
            raise HTTPException(status_code=502, detail="Proxy summarizer error")
        return r.json()["summary"]

# ---------------------------------------------------------------------------
# DB ops
# ---------------------------------------------------------------------------

def _insert_summary(conn: sqlite3.Connection, user_id: str, content: str, level: int,
                    ts_begin: str, ts_end: str) -> None:
    cur = conn.cursor()
    cur.execute(
        f"INSERT INTO {TABLE} (user_id, content, level, timestamp_begin, timestamp_end) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, content, level, ts_begin, ts_end),
    )

# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/summaries/user/{user_id}", response_model=UserSummaryList)
async def list_summaries(
    user_id: str = Path(...),
    limit: Optional[int] = Query(None, ge=1),
    level: Optional[int] = Query(None, ge=1),
):
    """List summaries for a user, optionally limited by count or level."""
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
        rows = cur.fetchall()
        return UserSummaryList(summaries=[UserSummary(*row) for row in rows])


@router.delete("/summaries/user/{user_id}", response_model=DeleteSummary)
async def delete_summaries(
    user_id: str = Path(...),
    body: DeleteRequest = Body(...),
):
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
    """Entry‑point: summarize oldest chunk if buffer is too long, then do cascade compression."""
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
