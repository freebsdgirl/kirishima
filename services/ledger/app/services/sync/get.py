from shared.models.ledger import CanonicalUserMessage

from shared.log_config import get_logger
logger = get_logger(f"ledger.{__name__}")

from app.util import _open_conn

import json
import tiktoken
from typing import List

TABLE = "user_messages"


def _ensure_first_user(messages):
    """Ensure the first message in the list has role 'user'"""
    for i, msg in enumerate(messages):
        if msg.role == "user":
            return messages[i:]
    return []


def _get_sync_buffer_helper(user_id: str = None) -> List[CanonicalUserMessage]:
    """
    Internal helper for retrieving the conversation buffer with token-based limiting.

    Returns the conversation history up to the configured token limit,
    ensuring the first message is a user message.

    Args:
        user_id: The user ID (defaults to config user_id if not provided)

    Returns:
        List[CanonicalUserMessage]: Conversation buffer limited by tokens
    """
    
    # Load configuration
    with open('/app/config/config.json') as f:
        _config = json.load(f)
    
    # Default to config user_id if not provided
    if not user_id:
        user_id = _config.get("user_id")
    
    # Get token limit from config
    token_limit = _config.get("conversation", {}).get("length", 4000)
    
    # Initialize tokenizer (using gpt-3.5-turbo encoding as default)
    try:
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    with _open_conn() as conn:
        cur = conn.cursor()
        cur.execute(f"SELECT * FROM {TABLE} WHERE user_id = ? ORDER BY id", (user_id,))
        colnames = [desc[0] for desc in cur.description]
        raw_messages = [dict(zip(colnames, row)) for row in cur.fetchall()]
        
        # Parse JSON fields
        for msg in raw_messages:
            if msg.get("tool_calls"):
                try:
                    msg["tool_calls"] = json.loads(msg["tool_calls"])
                except Exception:
                    msg["tool_calls"] = None
            if msg.get("function_call"):
                try:
                    msg["function_call"] = json.loads(msg["function_call"])
                except Exception:
                    msg["function_call"] = None
        
        # Convert to CanonicalUserMessage objects
        messages = [CanonicalUserMessage(**msg) for msg in raw_messages]
        
        # Filter out only assistant messages with empty content AND no tool calls
        messages = [
            msg for msg in messages
            if not (
                getattr(msg, 'role', None) == 'assistant' and 
                not getattr(msg, 'content', None) and 
                not getattr(msg, 'tool_calls', None)
            )
        ]
        
        # Apply token-based limiting from the end
        if token_limit:
            total_tokens = 0
            limited_messages = []
            
            # Work backwards through messages, counting tokens
            for msg in reversed(messages):
                content = getattr(msg, 'content', '') or ''
                msg_tokens = len(encoding.encode(content))
                
                if total_tokens + msg_tokens <= token_limit:
                    limited_messages.insert(0, msg)
                    total_tokens += msg_tokens
                else:
                    break
            
            messages = limited_messages
        
        # Ensure first message is user role
        messages = _ensure_first_user(messages)
        
        return messages
