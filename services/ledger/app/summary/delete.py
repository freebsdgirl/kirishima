"""
This module provides an API endpoint for deleting summary records from the ledger database.

It defines a FastAPI router with a DELETE endpoint `/summary` that allows deletion of summary entries
by either their unique ID or by specifying a time period and date. The database connection is configured
using settings from `/app/config/config.json`, and all deletions are performed on the `summaries` table.

Functions:
    _delete_summary(): Internal helper to delete summary records by ID or by period and date.
    delete_summary(): FastAPI endpoint to delete summary records by ID or by period and date.

    The number of deleted records wrapped in a `DeleteSummary` response model.
"""

from shared.models.ledger import DeleteSummary, SummaryDeleteRequest
from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

from typing import Optional
from fastapi import APIRouter, Query
from app.util import _open_conn

router = APIRouter()

TABLE = "summaries"


def _delete_summary(
    id: Optional[str] = None,
    period: Optional[str] = None,
    timestamp_begin: Optional[str] = None,
    timestamp_end: Optional[str] = None,
) -> int:
    """
    Internal helper to delete summary records by ID or by period and date. Returns number deleted.
    """
    from datetime import datetime, time
    conn = _open_conn()
    deleted_count = 0
    try:
        if id:
            # Delete by ID
            cur = conn.execute(f"DELETE FROM {TABLE} WHERE id = ?", (id,))
            deleted_count = cur.rowcount
        elif period:
            # Delete by period and date range
            clauses = ["summary_type = ?"]
            params = [period]
            
            if timestamp_begin:
                clauses.append("timestamp_begin >= ?")
                params.append(timestamp_begin)
            if timestamp_end:
                clauses.append("timestamp_end <= ?")
                params.append(timestamp_end)
                
            query = f"DELETE FROM {TABLE} WHERE " + " AND ".join(clauses)
            cur = conn.execute(query, tuple(params))
            deleted_count = cur.rowcount
        else:
            # If neither id nor period, do nothing
            pass
        conn.commit()
    finally:
        conn.close()
    return deleted_count


@router.delete("/summary", response_model=DeleteSummary)
def delete_summary(
    id: Optional[str] = Query(None, description="ID of the summary to delete."),
    period: Optional[str] = Query(None, description="Time period (e.g., 'morning', 'afternoon', 'daily', etc.)"),
    timestamp_begin: Optional[str] = Query(None, description="Lower bound for deletion timestamp range"),
    timestamp_end: Optional[str] = Query(None, description="Upper bound for deletion timestamp range"),
) -> DeleteSummary:
    """
    Delete summary filtered by ID or period and date.
    """
    deleted_count = _delete_summary(
        id=id, 
        period=period, 
        timestamp_begin=timestamp_begin, 
        timestamp_end=timestamp_end
    )
    return DeleteSummary(deleted=deleted_count)

