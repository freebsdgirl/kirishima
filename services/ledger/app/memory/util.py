from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from app.util import _open_conn

def memory_exists(memory_id: str) -> bool:
    """
    Check if a memory exists in the database by its ID.

    Args:
        memory_id (str): The unique identifier of the memory.

    Returns:
        bool: True if the memory exists, False otherwise.
    """
    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM memories WHERE id = ?", (memory_id,))
        exists = cur.fetchone() is not None
    logger.debug(f"Checked existence of memory ID {memory_id}: {exists}")
    return exists