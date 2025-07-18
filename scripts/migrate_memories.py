import sqlite3

# Source and destination DBs
SRC_DB = "memories.db"
DST_DB = "buffer.db"

# Columns in brain's memories table:
# id TEXT PRIMARY KEY, user_id TEXT, memory TEXT, created_at TEXT, access_count INTEGER DEFAULT 0, last_accessed TEXT, priority FLOAT, reviewed INTEGER DEFAULT 0

# Columns in ledger's memories table:
# id TEXT PRIMARY KEY, memory TEXT, created_at TEXT, access_count INTEGER DEFAULT 0, last_accessed TEXT, reviewed INTEGER DEFAULT 0

def migrate_memories():
    src_conn = sqlite3.connect(SRC_DB)
    dst_conn = sqlite3.connect(DST_DB)

    src_cur = src_conn.cursor()
    dst_cur = dst_conn.cursor()

    # --- Migrate memories table ---
    src_cur.execute("SELECT id, memory, created_at, access_count, last_accessed, reviewed FROM memories")
    rows = src_cur.fetchall()
    for row in rows:
        dst_cur.execute(
            "INSERT OR IGNORE INTO memories (id, memory, created_at, access_count, last_accessed, reviewed) VALUES (?, ?, ?, ?, ?, ?)",
            row
        )
    print(f"Migrated {len(rows)} memories.")

    # --- Migrate memory_tags table ---
    src_cur.execute("SELECT memory_id, tag FROM memory_tags")
    rows = src_cur.fetchall()
    for row in rows:
        dst_cur.execute(
            "INSERT OR IGNORE INTO memory_tags (memory_id, tag) VALUES (?, ?)",
            row
        )
    print(f"Migrated {len(rows)} memory_tags.")

    # --- Migrate memory_category table ---
    src_cur.execute("SELECT memory_id, category FROM memory_category")
    rows = src_cur.fetchall()
    for row in rows:
        dst_cur.execute(
            "INSERT OR IGNORE INTO memory_category (memory_id, category) VALUES (?, ?)",
            row
        )
    print(f"Migrated {len(rows)} memory_category.")

    # --- Migrate memory_topics table ---
    src_cur.execute("SELECT memory_id, topic_id FROM memory_topics")
    rows = src_cur.fetchall()
    for row in rows:
        dst_cur.execute(
            "INSERT OR IGNORE INTO memory_topics (memory_id, topic_id) VALUES (?, ?)",
            row
        )
    print(f"Migrated {len(rows)} memory_topics.")

    dst_conn.commit()
    src_conn.close()
    dst_conn.close()

if __name__ == "__main__":
    migrate_memories()