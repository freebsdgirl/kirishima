"""
API endpoint for retrieving summary records from the ledger SQLite database.
Supports filtering by ID, period, and date.
"""

from shared.models.ledger import Summary, SummaryMetadata, SummaryGetRequest
from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException, status
from app.util import _open_conn

router = APIRouter()
TABLE = "summaries"


def _get_summaries(
    id: Optional[str] = None,
    period: Optional[str] = None,
    timestamp_begin: Optional[str] = None,
    timestamp_end: Optional[str] = None,
    keywords: Optional[List[str]] = None,
    limit: Optional[int] = None,
) -> List[Summary]:
    """
    Retrieve summaries based on optional filtering criteria. (Internal helper)
    """
    conn = _open_conn()
    try:
        cur = conn.cursor()
        query = f"SELECT * FROM {TABLE}"
        clauses = []
        params = []
        if id:
            clauses.append("id = ?")
            params.append(id)
        if period:
            clauses.append("summary_type = ?")
            params.append(period)
        if timestamp_begin:
            clauses.append("timestamp_begin >= ?")
            params.append(timestamp_begin)
        if timestamp_end:
            clauses.append("timestamp_end <= ?")
            params.append(timestamp_end)
        if keywords:
            for kw in keywords:
                clauses.append("summary LIKE ?")
                params.append(f"%{kw}%")
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY timestamp_begin DESC"
        if limit:
            query += f" LIMIT {limit}"
        cur.execute(query, tuple(params))
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        summaries = []
        for row in rows:
            metadata = SummaryMetadata(
                summary_type=row[colnames.index('summary_type')] if 'summary_type' in colnames else None,
                timestamp_begin=row[colnames.index('timestamp_begin')] if 'timestamp_begin' in colnames else None,
                timestamp_end=row[colnames.index('timestamp_end')] if 'timestamp_end' in colnames else None,
            )
            summary = Summary(
                id=row[colnames.index('id')],
                content=row[colnames.index('summary')],
                metadata=metadata
            )
            summaries.append(summary)
        return summaries
    finally:
        conn.close()


@router.get("/summary", response_model=List[Summary])
def get_summary(
    id: Optional[str] = Query(None, description="Filter by summary ID."),
    period: Optional[str] = Query(None, description="Filter summaries by summary period ('morning', 'afternoon', 'daily', etc)."),
    timestamp_begin: Optional[str] = Query(None, description="Lower bound for summary timestamp (YYYY-MM-DD HH:MM:SS)."),
    timestamp_end: Optional[str] = Query(None, description="Upper bound for summary timestamp (YYYY-MM-DD HH:MM:SS)."),
    keywords: Optional[List[str]] = Query(None, description="List of keywords to search for in summary text."),
    limit: Optional[int] = Query(None, description="Maximum number of summaries to return."),
) -> List[Summary]:
    """
    Retrieve summaries based on optional filtering criteria.
    """
    try:
        summaries = _get_summaries(
            id=id,
            period=period,
            timestamp_begin=timestamp_begin,
            timestamp_end=timestamp_end,
            keywords=keywords,
            limit=limit,
        )
        if not summaries:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No summaries found for the given criteria"
            )
        return summaries
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error in get_summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred while retrieving summaries: {e}"
        )
