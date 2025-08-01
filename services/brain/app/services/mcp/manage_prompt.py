"""
MCP manage_prompt tool - Agent's system prompt management via MCP interface.

This module provides manage_prompt functionality via the MCP (Model Context Protocol) service.
It supports the following operations on agent-managed prompts:
- add: Add a new prompt entry with text and reasoning
- delete: Delete an existing prompt by ID  
- list: List all enabled prompts for the user

Each operation communicates with the brainlets SQLite database and returns a standardized
MCPToolResponse indicating success or failure, along with the result or error message.
Logging is provided for error handling and debugging purposes.

This tool is restricted to internal use only and not available to external clients like Copilot.
"""

from shared.models.mcp import MCPToolResponse
from typing import Dict, Any
import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")


async def manage_prompt(parameters: Dict[str, Any]) -> MCPToolResponse:
    """
    Manage agent's system prompts via MCP.
    Supports add, delete, and list operations.
    
    Actions:
    - add: Add a new prompt entry (requires prompt_text and reasoning)
    - delete: Delete a prompt by ID (requires prompt_id)
    - list: List all enabled prompts for the user
    """
    try:
        action = parameters.get("action")
        if not action:
            return MCPToolResponse(success=False, error="Action is required")
        
        if action == "add":
            return await _manage_prompt_add(parameters)
        elif action == "delete":
            return await _manage_prompt_delete(parameters)
        elif action == "list":
            return await _manage_prompt_list(parameters)
        else:
            return MCPToolResponse(success=False, error=f"Unknown action: {action}")
    
    except Exception as e:
        logger.error(f"Manage prompt tool error: {e}")
        return MCPToolResponse(success=False, error=str(e))


async def _manage_prompt_add(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Add a new prompt entry."""
    try:
        prompt_text = parameters.get("prompt_text")
        reasoning = parameters.get("reasoning")
        
        if not prompt_text or not reasoning:
            return MCPToolResponse(success=False, error="prompt_text and reasoning are required for adding a prompt")
        
        user_id = 'c63989a3-756c-4bdf-b0c2-13d01e129e02'  # Stub: replace with actual user_id logic

        with open('/app/config/config.json') as f:
            _config = json.load(f)
        
        db_path = _config['db']['brainlets']
        if not db_path or not Path(db_path).exists():
            return MCPToolResponse(success=False, error="Brainlets database not configured or does not exist")
        
        prompt_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute(
                "INSERT INTO prompt (id, user_id, prompt, reasoning, timestamp) VALUES (?, ?, ?, ?, ?)",
                (prompt_id, user_id, prompt_text, reasoning, timestamp)
            )
            conn.commit()
            
        result = {"status": "success", "action": "added", "id": prompt_id}
        return MCPToolResponse(success=True, result=result)
        
    except sqlite3.Error as e:
        logger.error(f"Database error in manage_prompt add: {e}")
        return MCPToolResponse(success=False, error=f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f"Error in manage_prompt add: {e}")
        return MCPToolResponse(success=False, error=str(e))


async def _manage_prompt_delete(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Delete a prompt entry by ID."""
    try:
        prompt_id = parameters.get("prompt_id")
        if not prompt_id:
            return MCPToolResponse(success=False, error="prompt_id is required for deleting a prompt")
        
        user_id = 'c63989a3-756c-4bdf-b0c2-13d01e129e02'  # Stub: replace with actual user_id logic

        with open('/app/config/config.json') as f:
            _config = json.load(f)
        
        db_path = _config['db']['brainlets']
        if not db_path or not Path(db_path).exists():
            return MCPToolResponse(success=False, error="Brainlets database not configured or does not exist")
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("DELETE FROM prompt WHERE id = ? AND user_id = ?", (prompt_id, user_id))
            conn.commit()
            
            if cursor.rowcount == 0:
                return MCPToolResponse(success=False, error="No prompt found with that ID for the user")
            
        result = {"status": "success", "action": "deleted", "id": prompt_id}
        return MCPToolResponse(success=True, result=result)
        
    except sqlite3.Error as e:
        logger.error(f"Database error in manage_prompt delete: {e}")
        return MCPToolResponse(success=False, error=f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f"Error in manage_prompt delete: {e}")
        return MCPToolResponse(success=False, error=str(e))


async def _manage_prompt_list(parameters: Dict[str, Any]) -> MCPToolResponse:
    """List all enabled prompts for the user."""
    try:
        user_id = 'c63989a3-756c-4bdf-b0c2-13d01e129e02'  # Stub: replace with actual user_id logic

        with open('/app/config/config.json') as f:
            _config = json.load(f)
        
        db_path = _config['db']['brainlets']
        if not db_path or not Path(db_path).exists():
            return MCPToolResponse(success=False, error="Brainlets database not configured or does not exist")
        
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("SELECT id, prompt, reasoning, timestamp FROM prompt WHERE user_id = ? AND enabled = 1", (user_id,))
            prompts = cursor.fetchall()
            
        if not prompts:
            result = {"status": "success", "action": "list", "prompts": []}
        else:
            # Return compact format: id|prompt
            prompt_list = [f"{row[0]}|{row[1]}" for row in prompts]
            result = {"status": "success", "action": "list", "prompts": prompt_list}
        
        return MCPToolResponse(success=True, result=result)
        
    except sqlite3.Error as e:
        logger.error(f"Database error in manage_prompt list: {e}")
        return MCPToolResponse(success=False, error=f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f"Error in manage_prompt list: {e}")
        return MCPToolResponse(success=False, error=str(e))
