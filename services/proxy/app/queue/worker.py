"""
This module defines the queue worker logic for processing ProxyTaskQueue tasks by sending payloads to the Ollama API.
Functions:
    send_to_ollama(payload):
        Asynchronously sends a payload to the Ollama API's generate endpoint, handling HTTP and connection errors,
        and returns the API response.
    queue_worker_main(queue: ProxyTaskQueue):
        Continuously processes tasks from a ProxyTaskQueue by sending their payloads to Ollama, handling both blocking
        and non-blocking tasks, and managing task results or callbacks accordingly.
"""
import app.config
from shared.models.proxy import OllamaRequest, OllamaResponse, OpenAIRequest, OpenAIResponse, AnthropicRequest, AnthropicResponse
from shared.models.queue import ProxyTaskQueue, ProxyTask

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

import httpx
import json

from fastapi import HTTPException, status

from app.queue.router import ollama_queue, openai_queue

with open('/app/config/config.json') as f:
    _config = json.load(f)

TIMEOUT = _config["timeout"]


async def send_to_ollama(request: OllamaRequest) -> OllamaResponse:
    """
    Send a payload to the Ollama API for generation.
    
    Sends an asynchronous HTTP POST request to the Ollama API's generate endpoint with the provided payload.
    Handles potential HTTP and request errors, logging details and raising appropriate HTTPExceptions.
    
    Args:
        payload (dict): The payload to send to the Ollama API for generation.
    
    Returns:
        httpx.Response: The response from the Ollama API containing the generated content.
    
    Raises:
        HTTPException: If there are HTTP status errors or connection issues with the Ollama API.
    """
    logger.debug(f"🦙 Request to Ollama API:\n{json.dumps(request.model_dump(), indent=4, ensure_ascii=False)}")

    payload = {
        "model": request.model,
        "prompt": request.prompt,
        **(request.options or {}),
        "stream": False,
        "raw": True
    }

    if request.format:
        payload['format'] = request.format

    # Send the POST request using an async HTTP client
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.post(f"{app.config.OLLAMA_URL}/api/generate", json=payload)
            response.raise_for_status()

        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from Ollama API: {http_err.response.status_code} - {http_err.response.text}")

            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from language model service: {http_err.response.text}"
            )

        except httpx.RequestError as req_err:
            logger.error(f"Request error connecting to Ollama API: {req_err}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}"
            )
        
        except Exception as e:
            logger.error(f"Unexpected error: {e}")

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error: {e}"
            )

    json_response = response.json()
    logger.debug(f"🦙 Response from Ollama API:\n{json.dumps(json_response, indent=4, ensure_ascii=False)}")

    json_response['response'] = json_response['response'].strip()

    ollama_response = OllamaResponse(**json_response)

    return ollama_response


async def send_to_openai(request: OpenAIRequest) -> OpenAIResponse:
    """
    Send a payload to the OpenAI API for generation.
    """
    logger.debug(f"🤖 Request to OpenAI API:\n{json.dumps(request.model_dump(), indent=4, ensure_ascii=False)}")

    # Normalize tool_calls to always be a list (OpenAI expects an array)
    def _normalize_tool_calls(messages):
        for msg in messages:
            if "tool_calls" in msg and msg["tool_calls"] is not None and not isinstance(msg["tool_calls"], list):
                msg["tool_calls"] = [msg["tool_calls"]]
        return messages

    payload = {
        "model": request.model,
        "messages": _normalize_tool_calls(request.messages),
        **(request.options or {})
    }
    if getattr(request, "tools", None):
        payload["tools"] = request.tools

        if getattr(request, "tool_choice", None):
            payload["tool_choice"] = request.tool_choice

    # Get OpenAI API key from config.json
    api_key = _config.get("openai", {}).get("api_key")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing OpenAI API key in config.json")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from OpenAI API: {http_err.response.status_code} - {http_err.response.text}")
            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from OpenAI: {http_err.response.text}"
            )
        except httpx.RequestError as req_err:
            logger.error(f"Request error connecting to OpenAI API: {req_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}"
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error: {e}"
            )

    json_response = response.json()
    logger.debug(f"🤖 Response from OpenAI API:\n{json.dumps(json_response, indent=4, ensure_ascii=False)}")

    # Parse OpenAI response to OpenAIResponse (you may need to adjust this)
    openai_response = OpenAIResponse.from_api(json_response)
    return openai_response


async def send_to_anthropic(request: AnthropicRequest) -> AnthropicResponse:
    """
    Send a payload to the Anthropic API for generation using their native Messages API.
    """
    
    # Build payload for Anthropic's native Messages API
    # Anthropic requires system messages to be in a top-level 'system' parameter, not in messages array
    # Anthropic also doesn't support "tool" role - tool results must be in "user" messages as tool_result blocks
    # Most importantly: every tool_use block MUST be immediately followed by tool_result blocks in the next message
    system_message = None
    filtered_messages = []
    
    i = 0
    while i < len(request.messages):
        message = request.messages[i]
        
        if message.get("role") == "system":
            # Extract system message content
            system_message = message.get("content", "")
            i += 1
        elif message.get("role") == "assistant":
            # Convert OpenAI-style tool_calls to Anthropic tool_use content blocks
            content = []
            
            # Add text content if present
            if message.get("content"):
                content.append({"type": "text", "text": message.get("content")})
            
            # Convert tool_calls to tool_use blocks
            tool_calls = message.get("tool_calls")
            tool_use_ids = []
            
            if tool_calls:
                if isinstance(tool_calls, list):
                    for tool_call in tool_calls:
                        if tool_call.get("type") == "function":
                            function = tool_call.get("function", {})
                            tool_use_block = {
                                "type": "tool_use",
                                "id": tool_call.get("id"),
                                "name": function.get("name"),
                                "input": json.loads(function.get("arguments", "{}")) if isinstance(function.get("arguments"), str) else function.get("arguments", {})
                            }
                            content.append(tool_use_block)
                            tool_use_ids.append(tool_call.get("id"))
                elif isinstance(tool_calls, dict):
                    # Handle single tool call as dict
                    if tool_calls.get("type") == "function":
                        function = tool_calls.get("function", {})
                        tool_use_block = {
                            "type": "tool_use",
                            "id": tool_calls.get("id"),
                            "name": function.get("name"),
                            "input": json.loads(function.get("arguments", "{}")) if isinstance(function.get("arguments"), str) else function.get("arguments", {})
                        }
                        content.append(tool_use_block)
                        tool_use_ids.append(tool_calls.get("id"))
            
            # Create assistant message
            new_message = {
                "role": "assistant",
                "content": content if content else message.get("content", "")
            }
            filtered_messages.append(new_message)
            i += 1
            
            # If we have tool_use blocks, we need to collect the corresponding tool results
            if tool_use_ids:
                tool_results = []
                
                # Look ahead for tool result messages that match our tool_use_ids
                j = i
                while j < len(request.messages) and request.messages[j].get("role") == "tool":
                    tool_msg = request.messages[j]
                    tool_call_id = tool_msg.get("tool_call_id")
                    if tool_call_id in tool_use_ids:
                        tool_result = {
                            "type": "tool_result",
                            "tool_use_id": tool_call_id,
                            "content": tool_msg.get("content", "")
                        }
                        tool_results.append(tool_result)
                        tool_use_ids.remove(tool_call_id)  # Remove found ID
                    j += 1
                
                # Create a user message with the tool results
                if tool_results:
                    tool_results_message = {
                        "role": "user",
                        "content": tool_results
                    }
                    filtered_messages.append(tool_results_message)
                
                # Skip the tool messages we just processed
                i = j
        elif message.get("role") == "user":
            # Regular user message
            new_message = {
                "role": "user",
                "content": message.get("content", "")
            }
            filtered_messages.append(new_message)
            i += 1
        elif message.get("role") == "tool":
            # Skip tool messages that weren't processed above (orphaned tool results)
            logger.warning(f"Orphaned tool result message: {message.get('tool_call_id')}")
            i += 1
        else:
            # For any other roles, keep as-is but log a warning
            logger.warning(f"Unexpected message role for Anthropic: {message.get('role')}")
            filtered_messages.append(message)
            i += 1

    payload = {
        "model": request.model,
        "messages": filtered_messages,
        "max_tokens": request.options.get("max_tokens", 1024) if request.options else 1024,
        **(request.options or {})
    }

    
    # Add system message as top-level parameter if present
    if system_message:
        payload["system"] = system_message
    
    # Handle tools - convert to Anthropic format if present
    if getattr(request, "tools", None):
        anthropic_tools = []
        for tool in request.tools:
            # Convert from OpenAI format to Anthropic format
            if tool.get("type") == "function":
                # Convert client-side OpenAI function to Anthropic custom tool
                function_def = tool.get("function", {})
                anthropic_tool = {
                    "type": "custom",
                    "name": function_def.get("name"),
                    "description": function_def.get("description"),
                    "input_schema": function_def.get("parameters", {})
                }
                anthropic_tools.append(anthropic_tool)
            elif tool.get("type") in ["web_search_20250305", "bash_20250124", "text_editor_20250124", "text_editor_20250429"]:
                # This is already in Anthropic server-side tool format
                anthropic_tools.append(tool)
            else:
                # Handle other tool types - for now skip unknown types
                logger.warning(f"Unknown tool type for Anthropic: {tool.get('type')}")
                continue
        
        if anthropic_tools:
            payload["tools"] = anthropic_tools

        # Anthropic's native API has different tool_choice format than OpenAI
        # For now, we'll omit tool_choice and let Anthropic decide automatically
        # tool_choice can be added later if needed with proper format
        # if getattr(request, "tool_choice", None):
        #     payload["tool_choice"] = request.tool_choice

    # Get Anthropic API key from config.json
    api_key = _config.get("anthropic", {}).get("api_key")
    if not api_key:
        raise HTTPException(status_code=500, detail="Missing Anthropic API key in config.json")

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json"
    }

    logger.debug(f"🎭 Request to Anthropic API:\n{json.dumps(payload, indent=4, ensure_ascii=False)}")
    
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as http_err:
            logger.error(f"HTTP error from Anthropic API: {http_err.response.status_code} - {http_err.response.text}")
            raise HTTPException(
                status_code=http_err.response.status_code,
                detail=f"Error from Anthropic: {http_err.response.text}"
            )
        except httpx.RequestError as req_err:
            logger.error(f"Request error connecting to Anthropic API: {req_err}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Connection error: {req_err}"
            )
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Unexpected error: {e}"
            )

    json_response = response.json()
    logger.debug(f"🎭 Response from Anthropic API:\n{json.dumps(json_response, indent=4, ensure_ascii=False)}")

    # Parse Anthropic native response format
    anthropic_response = AnthropicResponse.from_anthropic_native(json_response)
    return anthropic_response


async def queue_worker_main(queue: ProxyTaskQueue):
    """
    Process tasks from a ProxyTaskQueue by sending payloads to the correct provider.
    
    This async function continuously dequeues tasks from the provided queue, sends each task's 
    payload to Ollama, OpenAI, or Anthropic, and handles both blocking and non-blocking task types. For blocking tasks, 
    it sets the future's result or exception. For non-blocking tasks, it calls the provided callback.
    
    Args:
        queue (ProxyTaskQueue): The queue from which tasks will be dequeued and processed.
    
    Raises:
        Exception: If an error occurs during task processing, which is logged and potentially 
        set as an exception on the task's future for blocking tasks.
    """
    logger.debug("Queue worker started.")

    while True:
        task: ProxyTask = await queue.dequeue()
        logger.debug(f"Dequeued task {task.task_id} (priority={task.priority}, blocking={task.blocking})")

        try:
            # Dispatch based on payload type
            if isinstance(task.payload, OllamaRequest):
                result = await send_to_ollama(task.payload)
            elif isinstance(task.payload, OpenAIRequest):
                result = await send_to_openai(task.payload)
            elif isinstance(task.payload, AnthropicRequest):
                result = await send_to_anthropic(task.payload)
            else:
                raise Exception(f"Unknown payload type: {type(task.payload)}")

            if task.blocking and task.future:
                task.future.set_result(result)
                logger.debug(f"Set result for blocking task {task.task_id}")

            elif not task.blocking and task.callback:
                task.callback(result)
                logger.debug(f"Called callback for non-blocking task {task.task_id}")

        except Exception as e:
            logger.error(f"Error processing task {task.task_id}: {e}")
            if task.blocking and task.future and not task.future.done():
                task.future.set_exception(e)

        finally:
            queue.remove_task(task.task_id)

# In your main app startup, you should start a worker for each queue, e.g.:
# asyncio.create_task(queue_worker_main(ollama_queue))
# asyncio.create_task(queue_worker_main(openai_queue))
# asyncio.create_task(queue_worker_main(anthropic_queue))