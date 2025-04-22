"""conversation_summary_service.py — Daily/Weekly/Monthly summarisation for Discord conversations.

Design notes:
    • Token counts are ignored; this runs on a scheduler.
    • Periods: daily → weekly → monthly. We *never* delete summaries.
    • When creating a daily summary we summarise the window 48‑24 h ago.
      After success, delete buffer messages older than 24 h ago but *always* keep the
      newest `conversation_buffer_keep` messages regardless of age.
    • Weekly/Monthly simply combine earlier summaries; originals remain.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

import httpx
import sqlite3
import asyncio

from fastapi import APIRouter, Path, Query, HTTPException, status
from shared.log_config import get_logger
from shared.models.ledger import (
    ConversationSummary,
    ConversationSummaryList,
    DeleteSummary,
)
from app.config import (
    BUFFER_DB,
    conversation_buffer_keep,
)

logger = get_logger(__name__)
router = APIRouter()

TABLE = "conversation_summaries"
LEDGER_URL = "http://ledger:4200"
PROXY_URL = "http://proxy:4205"
UTC = timezone.utc

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _open_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(BUFFER_DB, timeout=5.0, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

async def _fetch_conversation_buffer(conv_id: str) -> List[dict]:
    async with httpx.AsyncClient() as cli:
        r = await cli.get(f"{LEDGER_URL}/ledger/conversation/{conv_id}/messages", timeout=60)
        r.raise_for_status()
        return r.json()

async def _delete_conversation_buffer_before(conv_id: str, timestamp_cut: str) -> None:
    """Delete all messages older than timestamp_cut *except* keep‑tail."""
    messages = await _fetch_conversation_buffer(conv_id)
    if len(messages) <= conversation_buffer_keep:
        return  # nothing to prune
    # messages ordered by id ASC from buffer endpoint
    to_consider = messages[: -conversation_buffer_keep]
    ids_to_delete = [m["id"] for m in to_consider if m["created_at"] < timestamp_cut]
    if not ids_to_delete:
        return
    async with httpx.AsyncClient() as cli:
        q_marks = ",".join(["?"] * len(ids_to_delete))
        # Internal delete – we expose an endpoint that accepts list? we don’t have one yet; quick loop:
        for chunk_id in ids_to_delete:
            await cli.delete(
                f"{LEDGER_URL}/ledger/conversation/{conv_id}/before/{chunk_id}", timeout=30
            )

async def _proxy_conv_summary(period: str, messages_or_summaries: List[str]) -> str:
    endpoint = {
        "daily": "conversation/daily",
        "weekly": "conversation/weekly",
        "monthly": "conversation/monthly",
    }[period]
    payload = {
        "messages" if period == "daily" else "summaries": messages_or_summaries,
    }
    async with httpx.AsyncClient() as cli:
        r = await cli.post(f"{PROXY_URL}/summary/{endpoint}", json=payload, timeout=120)
        if r.status_code != status.HTTP_201_CREATED:
            logger.error("Proxy %s summary failed %s: %s", period, r.status_code, r.text)
            raise HTTPException(status_code=502, detail="Proxy summariser error")
        return r.json()["summary"]

# ---------------------------------------------------------------------------
# DB insert
# ---------------------------------------------------------------------------

def _insert_conv_summary(
    conn: sqlite3.Connection,
    conv_id: str,
    content: str,
    period: str,
    ts_begin: str,
    ts_end: str,
) -> None:
    cur = conn.cursor()
    cur.execute(
        f"INSERT INTO {TABLE} (conversation_id, content, period, timestamp_begin, timestamp_end) "
        "VALUES (?, ?, ?, ?, ?)",
        (conv_id, content, period, ts_begin, ts_end),
    )

# ---------------------------------------------------------------------------
# GET endpoint
# ---------------------------------------------------------------------------

@router.get("/summaries/conversation/{conversation_id}", response_model=ConversationSummaryList)
async def list_conv_summaries(
    conversation_id: str = Path(...),
    period: Optional[str] = Query(None, regex="^(daily|weekly|monthly)$"),
    limit: Optional[int] = Query(None, ge=1),
):
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

# ---------------------------------------------------------------------------
# Daily summariser
# ---------------------------------------------------------------------------

@router.post("/summaries/conversation/{conversation_id}/daily/create", status_code=201)
async def create_daily_summary(conversation_id: str = Path(...)):
    now = datetime.now(UTC)
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

# ---------------------------------------------------------------------------
# Weekly / Monthly combiners (no deletes)
# ---------------------------------------------------------------------------

def _combine_and_store(conv_id: str, period_from: str, period_to: str, days: int):
    """Combine summaries from the last full `days` window into larger period."""
    now = datetime.now(UTC)
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
    ok = _combine_and_store(conversation_id, "daily", "weekly", 7)
    return {"status": "created" if ok else "ok", "detail": "weekly summariser"}

@router.post("/summaries/conversation/{conversation_id}/monthly/create", status_code=201)
async def create_monthly_summary(conversation_id: str = Path(...)):
    ok = _combine_and_store(conversation_id, "weekly", "monthly", 30)
    return {"status": "created" if ok else "ok", "detail": "monthly summariser"}
