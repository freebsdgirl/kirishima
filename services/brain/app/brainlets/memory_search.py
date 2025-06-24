""" example return:
{
    "memory_search": [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": {
                "id": "call_1M6VOGLfYfQLbvRjZNNRsyXw",
                "type": "function",
                "function": {
                    "name": "memory_search",
                    "arguments": "{\"keywords\":[\"mother\"]}"
                }
            }
        },
        {
            "role": "tool",
            "content": "{\"status\": \"ok\", \"memories\": []}",
            "tool_call_id": "call_1M6VOGLfYfQLbvRjZNNRsyXw"
        }
    ]
}
"""
from typing import Dict, Any
from shared.models.proxy import MultiTurnRequest
import json
import uuid

from shared.models.proxy import ProxyOneShotRequest
from app.message.singleturn import incoming_singleturn_message

from app.tools.memory_search import memory_search as memory_search_tool

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

async def memory_search(brainlets_output: Dict[str, Any], message: MultiTurnRequest):
    # Load config (for db path and model selection)
    with open('/app/config/config.json') as f:
        _config = json.load(f)


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
    chatlog = '\n'.join(chatlog_lines)

    # --- Build prompt for the model ---
    prompt = (
        "Using the conversation only as context, determine the keywords for the user's most recent messages.\n"
        "The keywords should help in retrieving relevant memories.\n"
        "Keywords should be comma-separated.\n\n"
        "{chatlog}\n\nKeywords:"
    ).format(chatlog=chatlog)

    # --- Get model/options from brainlets config ---
    brainlet_config = None
    for brainlet in _config.get('brainlets', []):
        if brainlet.get('name') == 'memory_search':
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
    keyword_string = response.response

    # Convert the comma-separated keyword string to a list of keywords
    keywords = [k.strip() for k in keyword_string.split(',') if k.strip()]

    tool_call_id = f"call_{uuid.uuid4().hex[:20]}"
    # Assistant function call entry
    assistant_entry = {
        "role": "assistant",
        "content": "",
        "tool_calls": {
            "id": tool_call_id,
            "type": "function",
            "function": {
                "name": "memory_search",
                "arguments": json.dumps({"keywords": keywords})
            }
        }
    }
    # Tool response entry
    tool_result = memory_search_tool(keywords)

    if not tool_result.get("memories"):
        return "No memories found for the provided keywords."

    tool_entry = {
        "role": "tool",
        "content": json.dumps(tool_result),
        "tool_call_id": tool_call_id
    }

    result = {"memory_search": [assistant_entry, tool_entry]}
    logger.debug(f"Returning from memory_search: {result}")
    return result