"""manage_prompt tool — CRUD for agent system prompts in brainlets DB.

Actions: add, delete, list.
Rewritten from scratch — the old MCP version imported a model that
no longer exists (MCPToolResponse).
"""

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from app.tools.base import tool, ToolResponse
from shared.log_config import get_logger

logger = get_logger(f"brain.{__name__}")

# Hardcoded user_id — same stub as the old implementation.
# TODO: replace with actual user resolution when multi-user lands.
_USER_ID = "c63989a3-756c-4bdf-b0c2-13d01e129e02"


def _get_db_path() -> str:
    """Resolve the brainlets DB path from config.json."""
    with open("/app/config/config.json") as f:
        config = json.load(f)
    return config["db"]["brainlets"]


@tool(
    name="manage_prompt",
    description="Manage agent's system prompts - add, delete, or list prompt entries (internal use only)",
    persistent=True,
    always=True,
    clients=["internal"],
    service="brainlets",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["add", "delete", "list"],
                "description": "Action to perform: add, delete, or list",
            },
            "prompt_id": {
                "type": "string",
                "description": "ID of the prompt to delete (required for delete action)",
            },
            "prompt_text": {
                "type": "string",
                "description": "Text content of the prompt (required for add action)",
            },
            "reasoning": {
                "type": "string",
                "description": "Reasoning for the prompt change (required for add action)",
            },
        },
        "required": ["action"],
    },
)
async def manage_prompt(parameters: dict) -> ToolResponse:
    """Dispatch to add / delete / list."""
    action = parameters.get("action")
    if not action:
        return ToolResponse(error="action is required")

    try:
        if action == "add":
            return await _add(parameters)
        elif action == "delete":
            return await _delete(parameters)
        elif action == "list":
            return await _list_prompts()
        else:
            return ToolResponse(error=f"Unknown action: {action}")
    except Exception as e:
        logger.error("manage_prompt error: %s", e, exc_info=True)
        return ToolResponse(error=str(e))


# ---------------------------------------------------------------------------
# Action handlers
# ---------------------------------------------------------------------------

async def _add(params: dict) -> ToolResponse:
    prompt_text = params.get("prompt_text")
    reasoning = params.get("reasoning")

    if not prompt_text or not reasoning:
        return ToolResponse(error="prompt_text and reasoning are required for add action")

    db_path = _get_db_path()
    if not db_path or not Path(db_path).exists():
        return ToolResponse(error="Brainlets database not configured or does not exist")

    prompt_id = str(uuid.uuid4())
    timestamp = datetime.now().isoformat()

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute(
                "INSERT INTO prompt (id, user_id, prompt, reasoning, timestamp) VALUES (?, ?, ?, ?, ?)",
                (prompt_id, _USER_ID, prompt_text, reasoning, timestamp),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.error("DB error in manage_prompt add: %s", e)
        return ToolResponse(error=f"Database error: {e}")

    return ToolResponse(result={"status": "success", "action": "added", "id": prompt_id})


async def _delete(params: dict) -> ToolResponse:
    prompt_id = params.get("prompt_id")
    if not prompt_id:
        return ToolResponse(error="prompt_id is required for delete action")

    db_path = _get_db_path()
    if not db_path or not Path(db_path).exists():
        return ToolResponse(error="Brainlets database not configured or does not exist")

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute(
                "DELETE FROM prompt WHERE id = ? AND user_id = ?",
                (prompt_id, _USER_ID),
            )
            conn.commit()

            if cursor.rowcount == 0:
                return ToolResponse(error="No prompt found with that ID for the user")
    except sqlite3.Error as e:
        logger.error("DB error in manage_prompt delete: %s", e)
        return ToolResponse(error=f"Database error: {e}")

    return ToolResponse(result={"status": "success", "action": "deleted", "id": prompt_id})


async def _list_prompts() -> ToolResponse:
    db_path = _get_db_path()
    if not db_path or not Path(db_path).exists():
        return ToolResponse(error="Brainlets database not configured or does not exist")

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute(
                "SELECT id, prompt, reasoning, timestamp FROM prompt WHERE user_id = ? AND enabled = 1",
                (_USER_ID,),
            )
            rows = cursor.fetchall()
    except sqlite3.Error as e:
        logger.error("DB error in manage_prompt list: %s", e)
        return ToolResponse(error=f"Database error: {e}")

    if not rows:
        return ToolResponse(result={"status": "success", "action": "list", "prompts": []})

    # Compact format: id|prompt_text
    prompt_list = [f"{row[0]}|{row[1]}" for row in rows]
    return ToolResponse(result={"status": "success", "action": "list", "prompts": prompt_list})
