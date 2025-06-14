from typing import Dict, Any
from shared.models.proxy import MultiTurnRequest
import json

from shared.models.proxy import ProxyOneShotRequest
from app.message.singleturn import incoming_singleturn_message

from app.tools.update_divoom import update_divoom

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

async def divoom(brainlets_output: Dict[str, Any], message: MultiTurnRequest):
    # Load config (for db path and model selection)
    with open('/app/shared/config.json') as f:
        _config = json.load(f)

    # Extract topic from the brainlet output
    topic = brainlets_output.get('topic_tracker', "")
    logger.debug(f"Extracted topic from brainlets_output: {topic}")

    # if the topic hasn't changed, then it will be empty - return early
    if not topic:
        logger.debug("No topic found, returning early from divoom")
        return

    # topic isn't actually what we want to search for, but rather the keywords
    # that we want to use for the memory search
    messages = message.messages
    # --- Filter messages: only 'user' or 'assistant' with non-empty content ---
    filtered = [
        m for m in messages
        if m.get('role') in ('user', 'assistant') and m.get('content')
    ]

    # --- Build human-readable chatlog ---
    chatlog_lines = []
    for m in filtered:
        if m['role'] == 'user':
            chatlog_lines.append(f"User: {m['content']}")
        elif m['role'] == 'assistant':
            chatlog_lines.append(f"Assistant: {m['content']}")
    filtered = chatlog_lines[-5:]
    chatlog = '\n'.join(filtered)

    # --- Build prompt for the model ---
    prompt = (
        "Using the conversation only as context, return a single emoji that best represents the topic or tone of the assistant's most recent message.\n"
        "{chatlog}\n\nEmoji:"
    ).format(chatlog=chatlog)

    # --- Get model/options from brainlets config ---
    brainlet_config = None
    for brainlet in _config.get('brainlets', []):
        if brainlet.get('name') == 'divoom':
            brainlet_config = brainlet
            break
    logger.debug(f"Brainlet config for divoom: {brainlet_config}")
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
    emoji_string = response.response

    update_divoom(emoji_string)

    return emoji_string