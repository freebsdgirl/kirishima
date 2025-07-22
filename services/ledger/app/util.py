import sqlite3
import json

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

def _open_conn() -> sqlite3.Connection:
    """
    Opens a SQLite database connection using the path specified in the configuration file.
    Reads the database path from '/app/config/config.json' under the key ["db"]["ledger"],
    establishes a connection with a 5-second timeout, sets the journal mode to WAL,
    and enables foreign key constraints.
    Returns:
        sqlite3.Connection: An open connection to the specified SQLite database.
    """
    with open('/app/config/config.json') as f:
        _config = json.load(f)
    db = _config["db"]["ledger"]
    conn = sqlite3.connect(db, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn
