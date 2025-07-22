from shared.models.ledger import Summary, SummaryMetadata

from shared.log_config import get_logger
logger = get_logger(f"ledger{__name__}")

from app.util import _open_conn

TABLE = "summaries"


def _insert_summary(summary: Summary) -> Summary:
    """
    Internal helper to insert (or upsert) a summary record in the SQLite ledger database.
    """
    conn = _open_conn()
    try:
        cur = conn.cursor()
        metadata = summary.metadata or SummaryMetadata(
            timestamp_begin=None,
            timestamp_end=None,
            summary_type=None
        )
        # Check for existing summary with same type and time range
        cur.execute(
            f"SELECT id FROM {TABLE} WHERE summary_type=? AND timestamp_begin=? AND timestamp_end=?",
            (metadata.summary_type, metadata.timestamp_begin, metadata.timestamp_end)
        )
        existing = cur.fetchone()
        if existing:
            cur.execute(f"DELETE FROM {TABLE} WHERE id=?", (existing[0],))
        # Insert new summary
        cur.execute(
            f"INSERT INTO {TABLE} (id, summary, timestamp_begin, timestamp_end, summary_type) VALUES (?, ?, ?, ?, ?)",
            (
                summary.id,
                summary.content,
                metadata.timestamp_begin,
                metadata.timestamp_end,
                metadata.summary_type
            )
        )
        conn.commit()
        return summary
    finally:
        conn.close()