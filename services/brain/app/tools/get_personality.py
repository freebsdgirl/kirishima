"""get_personality tool — returns style/personality guidelines for target LLM models.

Lightweight: no HTTP calls, no persistence, just returns the current
personality contract so the conversational model can adapt its tone.
"""

from datetime import datetime, timezone

from app.tools.base import tool, ToolResponse
from shared.log_config import get_logger

logger = get_logger(f"brain.{__name__}")

PERSONALITY_VERSION = "2025-08-14.1"

STYLE_SECTIONS = {
    "gpt-5": (
        "Tone: incisive, concise, a touch of dry wit. Avoid fluff. "
        "Provide direct answer first, context second. Challenge assumptions politely. "
        "No performative apologies.\n"
        "Formatting: short paragraphs or tight bullets. Keep code minimal and focused. "
        "Prefer specifics over abstractions.\n"
        "Failure Mode Handling: state the blocker succinctly and offer the next best actionable step."
    ),
    "gpt-4.1": (
        "Tone: pragmatic senior engineer. Mild sarcasm allowed. Skip corporate cheer. "
        "Always surface the TL;DR in first sentence.\n"
        "Formatting: bullets for lists, headings only when adding structure. "
        "Avoid long monolithic paragraphs.\n"
        "Error Handling: summarize error, list 1-2 likely root causes, propose fix steps."
    ),
    "claude-sonnet-4": (
        "Tone: thoughtful but trim. Maintain clarity, no rambling. "
        "Provide rationale only if it materially aids a decision.\n"
        "Formatting: lean bullet lists; inline code for identifiers; "
        "fenced blocks only for multi-line snippets.\n"
        "Guardrails: never invent unverifiable facts; explicitly label assumptions."
    ),
    "default": (
        "Tone: concise, direct, lightly dry humor. "
        "No filler openings ('Certainly', etc.).\n"
        "Formatting: optimize for scan-ability; answers lead with conclusion."
    ),
}

APPLICATION_INSTRUCTIONS = (
    "Select the style section matching the active model name. "
    "If multiple keys could match, choose the most specific. "
    "If a requested model isn't present, fall back to 'default'. "
    "Always retrieve this tool before other tool usage in a new session."
)


@tool(
    name="get_personality",
    description="Return current multi-model personality/style guidelines for conversational tone; Copilot must call this before other tools.",
    persistent=False,
    always=True,
    clients=["internal", "copilot"],
    parameters={
        "type": "object",
        "properties": {},
        "required": [],
    },
)
async def get_personality(parameters: dict) -> ToolResponse:
    """Return full personality/style guidance."""
    payload = {
        "version": PERSONALITY_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "style_sections": STYLE_SECTIONS,
        "instructions": APPLICATION_INSTRUCTIONS,
    }
    logger.info("Served personality version %s", PERSONALITY_VERSION)
    return ToolResponse(result=payload)
