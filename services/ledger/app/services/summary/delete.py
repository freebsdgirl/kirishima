from shared.models.ledger import SummaryDeleteRequest

from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

from app.util import _open_conn

TABLE = "summaries"


def _delete_summary(request: SummaryDeleteRequest) -> int:
    """
    Internal helper to delete summary records by ID or by period and date. Returns number deleted.
    Accepts a SummaryDeleteRequest model as its only argument.
    """
    conn = _open_conn()
    deleted_count = 0
    try:
        if request.id:
            cur = conn.execute(f"DELETE FROM {TABLE} WHERE id = ?", (request.id,))
            deleted_count = cur.rowcount
        elif request.period:
            clauses = ["summary_type = ?"]
            params = [request.period]
            if request.timestamp_begin:
                clauses.append("timestamp_begin >= ?")
                params.append(request.timestamp_begin)
            if request.timestamp_end:
                clauses.append("timestamp_end <= ?")
                params.append(request.timestamp_end)
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