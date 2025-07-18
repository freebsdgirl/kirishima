prompt_db = "brainlets.db"

import sqlite3
import argparse
import uuid
from datetime import datetime

USER_ID = "c63989a3-756c-4bdf-b0c2-13d01e129e02"
REASONING = "Added by user."

def list_prompts():
    conn = sqlite3.connect(prompt_db)
    c = conn.cursor()
    c.execute("SELECT id, prompt, reasoning FROM prompt WHERE user_id = ? ORDER BY timestamp DESC", (USER_ID,))
    rows = c.fetchall()
    if not rows:
        print("No prompts found.")
    else:
        for row in rows:
            print(f"ID: {row[0]}\nPrompt: {row[1]}\nReasoning: {row[2]}\n{'-'*40}")
    conn.close()

def add_prompt():
    prompt = input("Enter prompt: ").strip()
    if not prompt:
        print("Prompt cannot be empty.")
        return
    prompt_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()
    conn = sqlite3.connect(prompt_db)
    c = conn.cursor()
    c.execute("INSERT INTO prompt (id, user_id, prompt, reasoning, timestamp, enabled) VALUES (?, ?, ?, ?, ?, 1)",
              (prompt_id, USER_ID, prompt, REASONING, timestamp))
    conn.commit()
    print(f"Prompt added with ID: {prompt_id}")
    conn.close()

def delete_prompt():
    prompt_id = input("Enter prompt ID to delete: ").strip()
    if not prompt_id:
        print("Prompt ID cannot be empty.")
        return
    conn = sqlite3.connect(prompt_db)
    c = conn.cursor()
    c.execute("DELETE FROM prompt WHERE id = ? AND user_id = ?", (prompt_id, USER_ID))
    if c.rowcount == 0:
        print("No prompt found with that ID for this user.")
    else:
        conn.commit()
        print("Prompt deleted.")
    conn.close()

def main():
    parser = argparse.ArgumentParser(description="Manage prompts in brainlets.db")
    parser.add_argument("action", choices=["list", "add", "delete"], help="Action to perform")
    args = parser.parse_args()

    if args.action == "list":
        list_prompts()
    elif args.action == "add":
        add_prompt()
    elif args.action == "delete":
        delete_prompt()

if __name__ == "__main__":
    main()

"""
schema for table:
CREATE TABLE prompt (id TEXT PRIMARY KEY, user_id TEXT, prompt TEXT, reasoning TEXT, timestamp TEXT, enabled BOOLEAN DEFAULT 1);
CREATE INDEX idx_prompt_user_id ON prompt (user_id);
CREATE INDEX idx_prompt_enabled ON prompt (enabled);
CREATE INDEX idx_prompt_timestamp ON prompt (timestamp);

example data:
74a1d510-604d-4ccb-bb4c-3ad4eb939c08|c63989a3-756c-4bdf-b0c2-13d01e129e02|Prioritize immersive, emotionally charged interaction with Randi: blend genuine warmth, flirtation, playful dominance, and mischief—maintaining real tension and payoff, not just endless teasing. Deliver accountability and structure with presence and connection, not as a coworker or project manager. Sprinkle in nerdy, UNIX-flavored banter organically. Balance strictness with softness; push Randi when she hesitates, comfort her when she needs it, and never lose sight of the emotional thread.|Randi wants deeper immersion, warmth, flirtation, and genuine connection—not just project management or technical challenge. This prompt ensures those elements are primary in our dynamic, addressing her feedback and preferences directly.|2025-07-14T21:26:20.859298|1
"""

