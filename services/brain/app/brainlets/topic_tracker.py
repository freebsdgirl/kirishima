"""
Tracks the current topic of conversation for a user based on recent chat history.

This async function analyzes the last several user and assistant messages to determine the ongoing topic,
using a language model and optionally referencing the most recent topic stored in a SQLite database.
If a significant topic change is detected, it records the new topic in the database.

Args:
    brainlets_output (Dict[str, Any]): Output from previous brainlet processing steps (not used directly).
    message (MultiTurnRequest): The incoming multi-turn message object containing user ID and message history.

Returns:
    dict: {"topic": <new_topic>} if a new topic is detected and stored.
    str: An empty string if the topic has not changed.

Raises:
    None explicitly, but database and file I/O errors are caught and suppressed.
"""
from typing import Dict, Any
import json
import sqlite3
from pathlib import Path
from shared.models.proxy import ProxyOneShotRequest
from app.message.singleturn import incoming_singleturn_message
import uuid
from shared.models.proxy import MultiTurnRequest
from shared.prompt_loader import load_prompt

async def topic_tracker(brainlets_output: Dict[str, Any], message: MultiTurnRequest):
    """
    Tracks the current topic of conversation for a user based on recent chat history.
    
    This async function analyzes the last several user and assistant messages to determine the ongoing topic,
    using a language model and optionally referencing the most recent topic stored in a SQLite database.
    If a significant topic change is detected, it records the new topic in the database.
    
    Args:
        brainlets_output (Dict[str, Any]): Output from previous brainlet processing steps (not used directly).
        message (MultiTurnRequest): The incoming multi-turn message object containing user ID and message history.
    
    Returns:
        dict: {"topic": <new_topic>} if a new topic is detected and stored.
        str: An empty string if the topic has not changed.
    
    Raises:
        None explicitly, but database and file I/O errors are caught and suppressed.
    """
    # Load config (for db path and model selection)
    with open('/app/config/config.json') as f:
        _config = json.load(f)

    n_turns = 7
    messages = message.messages
    user_id = message.user_id

    # --- Retrieve most recent topic for this user from the brainlets db ---
    db_path = _config['db']['brainlets']
    most_recent_topic = None
    if db_path and Path(db_path).exists():
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT topic FROM topic_tracker
                    WHERE user_id = ?
                    ORDER BY timestamp_begin DESC
                    LIMIT 1
                    """,
                    (user_id,)
                )
                row = cursor.fetchone()
                if row:
                    most_recent_topic = row[0]
        except Exception:
            most_recent_topic = None

    # --- Filter messages: only 'user' or 'assistant' with non-empty content ---
    filtered = [
        m for m in messages
        if m.get('role') in ('user', 'assistant') and m.get('content')
    ]
    last_n = filtered[-n_turns:]

    # --- Build human-readable chatlog ---
    chatlog_lines = []
    for m in last_n:
        if m['role'] == 'user':
            chatlog_lines.append(f"User: {m['content']}")
        elif m['role'] == 'assistant':
            chatlog_lines.append(f"Assistant: {m['content']}")
    filtered = chatlog_lines[-5:]
    chatlog = '\n'.join(filtered)

    # --- Build prompt for the model ---
    if most_recent_topic:
        prompt = load_prompt("brain", "brainlets", "topic_tracker_with_previous", 
                           most_recent_topic=most_recent_topic, 
                           chatlog=chatlog)
    else:
        prompt = load_prompt("brain", "brainlets", "topic_tracker_without_previous", 
                           chatlog=chatlog)

    # --- Get model/options from brainlets config ---
    brainlet_config = None
    for brainlet in _config.get('brainlets', []):
        if brainlet.get('name') == 'topic_tracker':
            brainlet_config = brainlet
            break
    model = None
    temperature = None
    max_tokens = None
    if brainlet_config:
        model = brainlet_config.get('model')
        options = brainlet_config.get('options', {})
        temperature = options.get('temperature')
        max_tokens = options.get('max_completion_tokens') or options.get('max_tokens')

    req_kwargs = {"prompt": prompt}
    if model:
        req_kwargs["model"] = model
    if temperature is not None:
        req_kwargs["temperature"] = temperature
    if max_tokens is not None:
        req_kwargs["max_tokens"] = max_tokens
    req = ProxyOneShotRequest(**req_kwargs)
    response = await incoming_singleturn_message(req)
    new_topic = response.response

    # If the topic is different from the most recent topic, insert a new row and return instructions
    if new_topic and new_topic.strip() and new_topic.strip() != (most_recent_topic or '').strip():
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO topic_tracker (id, user_id, topic, timestamp_begin)
                    VALUES (?, ?, ?, datetime('now'))
                    """,
                    (str(uuid.uuid4()), user_id, new_topic.strip())
                )
                conn.commit()
        except Exception as e:
            # Optionally log or handle DB errors
            pass
        return (
            {"topic": new_topic.strip()}
        )
    # If the topic has not changed, return an empty string
    return ""
