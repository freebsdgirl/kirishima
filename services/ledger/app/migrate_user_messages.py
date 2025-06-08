import sqlite3

DB_PATH = "./shared/db/ledger/buffer.db"

def migrate_user_messages():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Add new columns if they do not exist
    cur.execute("PRAGMA table_info(user_messages)")
    columns = [row[1] for row in cur.fetchall()]

    if "model" not in columns:
        cur.execute("ALTER TABLE user_messages ADD COLUMN model TEXT")
    if "tool_calls" not in columns:
        cur.execute("ALTER TABLE user_messages ADD COLUMN tool_calls TEXT")
    if "function_call" not in columns:
        cur.execute("ALTER TABLE user_messages ADD COLUMN function_call TEXT")
    if "tool_call_id" not in columns:
        cur.execute("ALTER TABLE user_messages ADD COLUMN tool_call_id TEXT")
    conn.commit()

    # Set model to 'default' for all existing rows where model is NULL
    cur.execute("UPDATE user_messages SET model = 'default' WHERE model IS NULL")
    conn.commit()
    print("Migration complete. Columns ensured and model set to 'default' for existing rows.")
    conn.close()

if __name__ == "__main__":
    migrate_user_messages()
