from typing import List, Dict, Any
import json
import sqlite3
from pathlib import Path
from shared.models.proxy import ProxyOneShotRequest
from app.message.singleturn import incoming_singleturn_message
import uuid
from shared.models.proxy import MultiTurnRequest

async def topic_tracker(brainlets_output: Dict[str, Any], message: MultiTurnRequest):
    # Load config (for db path and model selection)
    with open('/app/shared/config.json') as f:
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
        prompt = (
            "Given the following conversation, and the most recent topic discussed ('{topic}'), "
            "determine the current subject matter or topic the user and assistant are discussing.\n"
            "Topics should be very broad and not too specific.\n"
            "Identify the main subject or ongoing theme of the conversation and avoid changing it unless there’s a significant shift.\n"
            "If the topic has significantly changed, reply with the new topic. If it has not significantly changed, reply with the same topic.\n"
            "The topic should be representative of the user's last comment as though it were the title of a chapter in a book unless it is a continuation of the previous conversation and not a complete change in topic.\n"
            "Respond with a single word or phrase representing the topic. Output only the topic—no formatting, no explanations, no commentary, no extra words.\n"
            "Most recent topic: {topic}\n\n"
            "{chatlog}\n\nCurrent topic:"
        ).format(topic=most_recent_topic, chatlog=chatlog)
    else:
        prompt = (
            "Given the following conversation, determine the current subject matter or topic "
            "the user and assistant are discussing. Respond with a concise word or phrase.\n\n"
            f"{chatlog}\n\nCurrent topic:"
        )

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
