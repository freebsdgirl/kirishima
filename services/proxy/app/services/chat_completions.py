from shared.models.proxy import MultiTurnRequest, ProxyResponse, OllamaRequest, OpenAIRequest, AnthropicRequest
from shared.models.prompt import BuildSystemPrompt

from app.services.util import _build_multiturn_prompt, _resolve_model_provider_options
from app.prompts.dispatcher import get_system_prompt

from app.services.queue import ollama_queue, openai_queue, anthropic_queue
from shared.models.queue import ProxyTask
import uuid
import asyncio

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

import json

from datetime import datetime
from dateutil import tz

local_tz = tz.tzlocal()
ts_with_offset = datetime.now(local_tz).isoformat(timespec="seconds")

from fastapi import HTTPException, status

async def _chat_completions(request: MultiTurnRequest) -> ProxyResponse:
    """ 
    Handle multi-turn API requests by generating prompts for language models.

    Processes a multi-turn conversation request, validates model compatibility,
    builds an instruct-style prompt, and sends a request to the Ollama API.
    Returns a ProxyResponse with the generated text and metadata.

    Args:
        request (ProxyMultiTurnRequest): Multi-turn conversation request details.

    Returns:
        ProxyResponse: Generated response from the language model.

    Raises:
        HTTPException: If the model is not instruct-compatible or API request fails.
    """
    logger.debug(f"/api/multiturn Request:\n{json.dumps(request.model_dump(), indent=4, ensure_ascii=False)}")

    with open('/app/config/config.json') as f:
        _config = json.load(f)

    TIMEOUT = _config["timeout"]

    # resolve provider/model/options from mode
    provider, model, options = _resolve_model_provider_options(request.model)
    logger.debug(f"Resolved provider/model/options: {provider}, {model}, {options}")

    # if the model is auto, we query the LLM to resolve the provider/model/options
    if request.model == "auto":
        prompt = f"""
Given the following conversation history, determine the best openai model to use for generating a response. Return the model name. Do not return any other text or explanation. Return gpt-4.1 for technical or work discussions or gpt-4o for general, casual, or personal discussions. Consider the most recent message as the primary context for determining the model.
Conversation history:

{request.messages}"""
        payload = OpenAIRequest(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options=options
        )
        queue_to_use = openai_queue

        # Create a blocking ProxyTask
        task_id = str(uuid.uuid4())
        future = asyncio.Future()
        task = ProxyTask(
            priority=1,
            task_id=task_id,
            payload=payload,
            blocking=True,
            future=future,
            callback=None
        )
        await queue_to_use.enqueue(task)

        try:
            result = await asyncio.wait_for(future, timeout=TIMEOUT)
        except asyncio.TimeoutError:
            queue_to_use.remove_task(task_id)
            raise HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Task timed out"
            )

        queue_to_use.remove_task(task_id)

        provider, model, options = _resolve_model_provider_options("default")

    # now get your dynamic system prompt
    system_prompt = get_system_prompt(
        BuildSystemPrompt(
            memories=request.memories,
            mode=request.model or 'default',
            platform=request.platform or 'api',
            summaries=request.summaries,
            username=request.username or 'Randi',
            timestamp=datetime.now().isoformat(timespec="seconds"),
            agent_prompt=request.agent_prompt or None,
        ),
        provider=provider,
        mode=request.model or 'default'
    )

    # build the full instruct‑style prompt
    full_prompt = _build_multiturn_prompt(request.messages, system_prompt)

    # Branch on provider and construct provider-specific request/payload
    if provider == "ollama":
        payload = OllamaRequest(
            model=model,
            prompt=full_prompt,
            temperature=options.get('temperature'),
            max_tokens=options.get('max_tokens'),
            stream=options.get('stream', False),
            raw=True
        )
        queue_to_use = ollama_queue
    elif provider == "openai":
          # Local import to avoid circular
        # Prepend system prompt as a system message for OpenAI
        openai_messages = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + request.messages
        payload = OpenAIRequest(
            model=model,
            messages=openai_messages,
            options=options,
            tools=request.tools,
            tool_choice="auto"  # Use auto tool choice for OpenAI
        )
        queue_to_use = openai_queue
    elif provider == "anthropic":
        # Prepend system prompt as a system message for Anthropic
        anthropic_messages = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + request.messages
        payload = AnthropicRequest(
            model=model,
            messages=anthropic_messages,
            options=options,
            tools=request.tools,
            tool_choice="auto"  # Use auto tool choice for Anthropic
        )
        queue_to_use = anthropic_queue
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")

    # Create a blocking ProxyTask
    task_id = str(uuid.uuid4())
    future = asyncio.Future()
    task = ProxyTask(
        priority=1,
        task_id=task_id,
        payload=payload,
        blocking=True,
        future=future,
        callback=None
    )
    await queue_to_use.enqueue(task)

    try:
        result = await asyncio.wait_for(future, timeout=TIMEOUT)
    except asyncio.TimeoutError:
        queue_to_use.remove_task(task_id)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Task timed out"
        )

    # result is a provider-specific response; normalize to ProxyResponse
    proxy_response = ProxyResponse(
        response=getattr(result, 'response', None),
        eval_count=getattr(result, 'eval_count', None),
        prompt_eval_count=getattr(result, 'prompt_eval_count', None),
        tool_calls=getattr(result, 'tool_calls', None),
        function_call=getattr(result, 'function_call', None),
        timestamp=datetime.now().isoformat()
    )

    # Remove tool execution logic: proxy should not process tool calls

    queue_to_use.remove_task(task_id)

    return proxy_response