"""
This is for the summaries table in chromadb. Instead of using the chromadb service, we'll connect directly to the database.
"""


ledger_db = "../shared/db/ledger/buffer.db"
import sqlite3

"""
ledger table schema

CREATE TABLE IF NOT EXISTS summaries (
    id                  TEXT PRIMARY KEY, -- UUID
    summary             TEXT,
    timestamp_begin     DATETIME NOT NULL,
    timestamp_end       DATETIME NOT NULL,
    summary_type        TEXT
);
"""
conn = sqlite3.connect(ledger_db, timeout=5.0)
conn.execute("PRAGMA journal_mode=WAL;")

summaries_db = "../shared/db/chromadb/"
from chromadb import PersistentClient
client = PersistentClient(path=summaries_db)

collection = client.get_collection('summary')

results = collection.get()
"""
example chromadb metadata entry:
{'timestamp_begin': '2025-04-29 06:25:02.940', 'timestamp_end': '2025-04-29 22:02:53.045', 'user_id': 'c63989a3-756c-4bdf-b0c2-13d01e129e02', 'summary_type': 'daily'}, 
"""
summaries = []
for i in range(len(results["ids"])):
    id = results['ids'][i]
    content = results['documents'][i]
    metadata = results['metadatas'][i]

    conn.execute(
        "INSERT OR REPLACE INTO summaries (id, summary, timestamp_begin, timestamp_end, summary_type) VALUES (?, ?, ?, ?, ?)",
        (id, content, metadata['timestamp_begin'], metadata['timestamp_end'], metadata['summary_type'] )
    )
    conn.commit()

