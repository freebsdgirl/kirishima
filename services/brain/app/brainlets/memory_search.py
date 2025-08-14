"""
Performs a memory search based on the most recent user and assistant messages in a conversation.

This function:
- Loads configuration for database path and model selection.
- Filters the conversation messages to include only those from the user or assistant with non-empty content.
- Builds a human-readable chat log from the filtered messages.
- Constructs a prompt to extract keywords from the conversation using a language model.
- Retrieves model parameters from the configuration.
- Sends the prompt to a language model to obtain relevant keywords.
- Uses the extracted keywords to perform a memory search via a tool function.
- Constructs and returns a structured result containing the assistant's function call and the tool's response.

Args:
    brainlets_output (Dict[str, Any]): Output from previous brainlets (not used in this function).
    message (MultiTurnRequest): The incoming multi-turn request containing the conversation messages.

Returns:
    dict or str: A dictionary containing the assistant's function call and the tool's response if memories are found,
                 otherwise a string indicating no memories were found.
"""
from typing import Dict, Any
from shared.models.proxy import MultiTurnRequest, SingleTurnRequest
import json
import uuid
import os
import httpx

from app.message.singleturn import incoming_singleturn_message

from app.tools.memory import memory_search_tool
from shared.prompt_loader import load_prompt

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")

async def memory_search(brainlets_output: Dict[str, Any], message: MultiTurnRequest):
    """
    Performs a memory search based on the most recent conversation messages.
    
    This function extracts keywords from the conversation using a language model,
    then uses those keywords to search for relevant memories.
    
    Args:
        brainlets_output (Dict[str, Any]): Output from previous brainlets (not used in this function).
        message (MultiTurnRequest): The incoming multi-turn request containing conversation messages.
    
    Returns:
        dict or str: A dictionary containing the assistant's function call and tool's response if memories are found,
                     otherwise a string indicating no memories were found.
    """
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
    prompt = load_prompt("brain", "brainlets", "memory_search", chatlog=chatlog)

    # --- Get model/options from brainlets config ---
    brainlet_config = None
    for brainlet in _config.get('brainlets', []):
        if brainlet.get('name') == 'memory_search':
            brainlet_config = brainlet
            break
    model = None
    if brainlet_config:
        model = brainlet_config.get('model')  # Interpreted as a mode name for SingleTurnRequest

    # Build SingleTurnRequest (mode-style). Fallback to 'default' if not set.
    singleturn_req = SingleTurnRequest(model=model or 'default', prompt=prompt)
    response = await incoming_singleturn_message(singleturn_req)
    keyword_response = response.response

    # Parse the JSON response from the LLM
    try:
        keywords_with_weights = json.loads(keyword_response.strip())
        if not isinstance(keywords_with_weights, dict):
            raise ValueError("Response is not a dictionary")
        
        # Normalize keywords to lowercase for consistency
        keywords_with_weights = {k.lower(): v for k, v in keywords_with_weights.items()}
        
        # Extract just the keywords for memory search
        keywords = list(keywords_with_weights.keys())
        
        # Update the heatmap with weighted keywords
        try:
            ledger_port = os.getenv("LEDGER_PORT", 4203)
            async with httpx.AsyncClient(timeout=60) as client:
                heatmap_response = await client.post(
                    f'http://ledger:{ledger_port}/context/update_heatmap',
                    json={"keywords": keywords_with_weights}
                )
                heatmap_response.raise_for_status()
                logger.debug(f"Heatmap updated: {heatmap_response.json()}")
        except Exception as e:
            logger.warning(f"Failed to update heatmap: {e}")
            # Continue with memory search even if heatmap update fails
            
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse keywords JSON: {e}. Falling back to comma-separated parsing.")
        # Fallback to old comma-separated format
        keywords = [k.strip().lower() for k in keyword_response.split(',') if k.strip()]
        keywords_with_weights = {k: "medium" for k in keywords}  # Default weight

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
    
    # NEW: Get contextual memories based on heatmap scores
    try:
        ledger_port = os.getenv("LEDGER_PORT", 4203)
        async with httpx.AsyncClient(timeout=60) as client:
            context_response = await client.get(
                f'http://ledger:{ledger_port}/context/?limit=5'
            )
            context_response.raise_for_status()
            context_data = context_response.json()
            memories = context_data.get("memories", [])
            
        if not memories:
            return "No contextual memories found."
            
        # Format memories for tool response (just the content, no metadata)
        memory_text = [f"{memory}\n" for memory in memories]
        
    except Exception as e:
        logger.error(f"Failed to get contextual memories: {e}")
        return "Error retrieving contextual memories."
    
    # OLD MEMORY SEARCH CODE (commented out)
    # # Tool response entry
    # tool_result = await memory_search_tool(keywords=keywords)

    # if not tool_result.get("memories"):
    #     return "No memories found for the provided keywords."

    # # Only keep 'id' and 'memory' fields in each memory
    # minimal_memories = [
    #     {"id": m.get("id"), "memory": m.get("memory"), "created_at": m.get("created_at")} for m in tool_result["memories"]
    # ]
    # tool_result = {"memories": minimal_memories}
    # 
    # # limit to the first 5 memories
    # if len(minimal_memories) > 5:
    #     minimal_memories = minimal_memories[:5]

    # memory_text = [
    #     f"{m['id']}|{m['memory']}|{m['created_at']}\n" for m in minimal_memories
    # ]

    # if not memory_text:
    #     logger.debug("No memories found for the provided keywords.")
    #     return "No memories found for the provided keywords."

    tool_entry = {
        "role": "tool",
        "content": ''.join(memory_text),
        "tool_call_id": tool_call_id
    }

    result = {"memory_search": [assistant_entry, tool_entry]}
    logger.debug(f"Returning from memory_search: {result}")
    return result