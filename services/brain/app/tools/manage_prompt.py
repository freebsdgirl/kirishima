import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path

def manage_prompt(action: str, prompt_id: str = None, prompt_text: str = None, reasoning: str = None):
    """
    Manage prompts in the brainlets database.
    
    Args:
        action (str): 'add', 'update', 'delete', or 'list'.
        prompt_id (str, optional): The ID of the prompt to manage.
        prompt_text (str, optional): The text of the prompt to add or update.
        reasoning (str, optional): The reasoning for the prompt.
    
    Returns:
        dict: Result of the action performed.
    """
    user_id = 'c63989a3-756c-4bdf-b0c2-13d01e129e02'  # Stub: replace with actual user_id logic

    with open('/app/shared/config.json') as f:
        _config = json.load(f)
    
    db_path = _config['db']['brainlets']
    if not db_path or not Path(db_path).exists():
        return {"status": "error", "error": "Brainlets database not configured or does not exist."}
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            
            if action == 'add':
                if not prompt_text or not reasoning:
                    return {"status": "error", "error": "prompt_text and reasoning are required for adding a prompt."}
                prompt_id = str(uuid.uuid4())
                timestamp = datetime.now().isoformat()
                cursor.execute(
                    "INSERT INTO prompt (id, user_id, prompt, reasoning, timestamp) VALUES (?, ?, ?, ?, ?)",
                    (prompt_id, user_id, prompt_text, reasoning, timestamp)
                )
                conn.commit()
                return {"status": "success", "action": "added", "id": prompt_id}
            
            elif action == 'update':
                if not prompt_id or not prompt_text or not reasoning:
                    return {"status": "error", "error": "prompt_id, prompt_text and reasoning are required for updating a prompt."}
                cursor.execute(
                    "UPDATE prompt SET prompt = ?, reasoning = ? WHERE id = ? AND user_id = ?",
                    (prompt_text, reasoning, prompt_id, user_id)
                )
                conn.commit()
                return {"status": "success", "action": "updated"}
            
            elif action == 'delete':
                if not prompt_id:
                    return {"status": "error", "error": "prompt_id is required for deleting a prompt."}
                cursor.execute("DELETE FROM prompt WHERE id = ? AND user_id = ?", (prompt_id, user_id))
                conn.commit()
                if cursor.rowcount == 0:
                    return {"status": "error", "error": "No prompt found with that ID for the user."}
                return {"status": "success", "action": "deleted", "id": prompt_id}
            elif action == 'list':
                cursor.execute("SELECT id, prompt, reasoning, timestamp FROM prompt WHERE user_id = ? AND enabled = 1", (user_id,))
                prompts = cursor.fetchall()
                if not prompts:
                    return {"status": "success", "action": "list", "prompts": []}
                prompt_list = [{"id": row[0], "prompt": row[1], "reasoning": row[2], "timestamp": row[3]} for row in prompts]
                return {"status": "success", "action": "list", "prompts": prompt_list}
            else:
                return {"status": "error", "error": "Invalid action. Use 'add', 'update', 'delete', or 'list'."}
    except sqlite3.Error as e:
        return {"status": "error", "error": str(e)}
# Example usage:
# result = manage_prompt('add', 'user123', prompt_text='What is AI?', reasoning='To understand the basics of AI.')
# result = manage_prompt('list', 'user123')
# result = manage_prompt('update', 'user123', prompt_id='some-id', prompt_text='Updated prompt text', reasoning='Updated reasoning.')
# result = manage_prompt('delete', 'user123', prompt_id='some-id')
