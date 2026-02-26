"""stickynotes tool — persistent, context-aware reminders via the stickynotes microservice.

Actions: create, list, snooze, resolve.

Also exports check_stickynotes() for pre-injection of due notes into conversations
(called by multiturn before the LLM, not by the LLM itself).
"""

import json
import os
import uuid

import httpx

from app.tools.base import tool, ToolResponse
from app.util import get_admin_user_id
from shared.log_config import get_logger

logger = get_logger(f"brain.{__name__}")

_STICKYNOTES_BASE = os.getenv("STICKYNOTES_URL", "http://stickynotes:4214")
_TIMEOUT = 30


@tool(
    name="stickynotes",
    description="Manage persistent reminders and sticky notes - create, list, snooze, or resolve notes with optional due dates and recurring schedules",
    persistent=True,
    always=False,
    clients=["internal"],
    service="stickynotes",
    guidance="Use ISO 8601 format for dates (e.g. 2026-02-27T09:00:00). For recurring notes, use ISO 8601 repeating intervals (e.g. R/P1D for daily, R/P7D for weekly). Snooze durations use ISO 8601 durations (e.g. PT1H for 1 hour, P1D for 1 day).",
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list", "snooze", "resolve"],
                "description": "The action to perform on sticky notes",
            },
            "text": {
                "type": "string",
                "description": "Content of the sticky note (required for create)",
            },
            "date": {
                "type": "string",
                "description": "Due date in ISO 8601 format, e.g. 2026-02-27T09:00:00 (required for create)",
            },
            "periodicity": {
                "type": "string",
                "description": "ISO 8601 repeating interval for recurring notes, e.g. R/P1D for daily (optional, create only)",
            },
            "id": {
                "type": "string",
                "description": "Sticky note ID (required for snooze and resolve)",
            },
            "snooze": {
                "type": "string",
                "description": "ISO 8601 duration to snooze for, e.g. PT1H for 1 hour (required for snooze)",
            },
        },
        "required": ["action"],
    },
)
async def stickynotes(parameters: dict) -> ToolResponse:
    """Execute a stickynotes action."""
    action = parameters.get("action")
    user_id = await get_admin_user_id()

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            if action == "create":
                text = parameters.get("text")
                date = parameters.get("date")
                if not text or not date:
                    return ToolResponse(error="'text' and 'date' are required for create action")
                payload = {"text": text, "due": date, "user_id": user_id}
                periodicity = parameters.get("periodicity")
                if periodicity:
                    payload["periodicity"] = periodicity
                logger.info("Creating sticky note: %s (due: %s)", text[:50], date)
                response = await client.post(f"{_STICKYNOTES_BASE}/create", json=payload)

            elif action == "list":
                logger.info("Listing sticky notes for user %s", user_id)
                response = await client.get(
                    f"{_STICKYNOTES_BASE}/list", params={"user_id": user_id}
                )

            elif action == "snooze":
                note_id = parameters.get("id")
                snooze_time = parameters.get("snooze")
                if not note_id or not snooze_time:
                    return ToolResponse(error="'id' and 'snooze' are required for snooze action")
                logger.info("Snoozing note %s for %s", note_id, snooze_time)
                response = await client.post(
                    f"{_STICKYNOTES_BASE}/snooze/{note_id}",
                    params={"snooze_time": snooze_time},
                )

            elif action == "resolve":
                note_id = parameters.get("id")
                if not note_id:
                    return ToolResponse(error="'id' is required for resolve action")
                logger.info("Resolving note %s", note_id)
                response = await client.get(f"{_STICKYNOTES_BASE}/resolve/{note_id}")

            else:
                return ToolResponse(error=f"Unknown action: {action}")

            response.raise_for_status()
            return ToolResponse(result=response.json())

    except httpx.HTTPStatusError as e:
        logger.error("Stickynotes %s failed (HTTP %d): %s", action, e.response.status_code, e.response.text)
        return ToolResponse(error=f"Stickynotes service returned {e.response.status_code}: {e.response.text}")
    except Exception as e:
        logger.error("Stickynotes %s failed: %s", action, e, exc_info=True)
        return ToolResponse(error=f"Stickynotes {action} failed: {e}")


# ---------------------------------------------------------------------------
# Pre-injection utility (not an LLM tool — called by multiturn before proxy)
# ---------------------------------------------------------------------------
async def check_stickynotes(user_id: str) -> list:
    """Check for due sticky notes and return simulated tool call messages.

    Returns a list of message dicts (assistant tool_call + tool result) to inject
    into the conversation, or an empty list if nothing is due.
    """
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            response = await client.get(
                f"{_STICKYNOTES_BASE}/check", params={"user_id": user_id}
            )
            response.raise_for_status()
            notes = response.json()
    except Exception as e:
        logger.warning("check_stickynotes failed: %s", e)
        return []

    if not notes:
        return []

    tool_call_id = str(uuid.uuid4())
    return [
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": tool_call_id,
                    "type": "function",
                    "function": {
                        "name": "stickynotes",
                        "arguments": json.dumps({"action": "check", "user_id": user_id}),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps(notes),
        },
    ]