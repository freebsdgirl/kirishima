"""Tool router — cheap LLM call to select relevant tools per message.

With only 4 tools (3 always-on, 1 routed), this is infrastructure for when
the tool count grows. Currently github_issue is the only routed tool.

Usage:
    from app.tools.router import route_tools
    from app.tools import get_routed_tools_catalog

    catalog = get_routed_tools_catalog()
    selected = await route_tools(user_message, catalog)
    # selected is a list of tool name strings
"""

import json
from typing import Dict, List

import httpx

from shared.log_config import get_logger

logger = get_logger(f"brain.{__name__}")

# Router prompt — kept small for cheap model consumption (~500 tokens in)
_ROUTER_PROMPT = """You are a tool router. Given a user message, decide which tools (if any) are relevant.

Available tools:
{tool_catalog}

User message: "{user_message}"

Return a JSON array of tool names that are relevant, or an empty array if none apply.
When in doubt, include the tool. Return ONLY the JSON array, no other text."""


async def route_tools(
    user_message: str,
    catalog: Dict[str, str],
    mode: str = "router",
    recent_context: str = "",
) -> List[str]:
    """Determine which routed tools are relevant for a user message.

    Args:
        user_message: The user's current message.
        catalog: {tool_name: description} dict of routable tools.
        mode: LLM mode to use (should be a cheap/fast model).
        recent_context: Optional last 2-3 messages for additional context.

    Returns:
        List of tool name strings. On any failure, returns ALL tool names
        from the catalog (safe fallback — wastes tokens but doesn't miss tools).
    """
    if not catalog:
        return []

    # Build the catalog text
    catalog_text = "\n".join(f"- {name}: {desc}" for name, desc in catalog.items())

    prompt_text = _ROUTER_PROMPT.format(
        tool_catalog=catalog_text,
        user_message=user_message,
    )

    # If there's recent context, prepend it
    if recent_context:
        prompt_text = f"Recent conversation context:\n{recent_context}\n\n{prompt_text}"

    try:
        # Call proxy singleturn with the cheap router mode
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "http://proxy:4201/singleturn",
                json={
                    "model": mode,
                    "prompt": prompt_text,
                },
            )
            response.raise_for_status()
            data = response.json()

        # Extract the response text
        response_text = data.get("response", "[]").strip()

        # Parse JSON array from response — handle markdown code blocks
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(
                line for line in lines if not line.startswith("```")
            ).strip()

        selected = json.loads(response_text)

        if not isinstance(selected, list):
            logger.warning("Router returned non-list: %s; falling back to all tools", selected)
            return list(catalog.keys())

        # Filter to only valid tool names
        valid = [name for name in selected if name in catalog]
        logger.info("Router selected %d/%d tools: %s", len(valid), len(catalog), valid)
        return valid

    except Exception as e:
        # On any failure, include all routed tools (safe fallback)
        logger.warning("Tool router failed (%s); including all %d routed tools", e, len(catalog))
        return list(catalog.keys())
