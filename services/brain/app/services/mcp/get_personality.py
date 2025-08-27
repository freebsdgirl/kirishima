"""get_personality MCP tool.

Returns style / personality guidelines for different target LLM models so that
clients (e.g. Copilot) can dynamically pull the latest tone contract instead of
hardcoding it. Lightweight: no persistence, no caching complexity.
"""
from datetime import datetime, timezone
from shared.models.mcp import ToolCallResponse
from shared.log_config import get_logger

logger = get_logger("brain.mcp.get_personality")

# Simple version stamp; update manually when changing content.
PERSONALITY_VERSION = "2025-08-14.1"

# Style definitions keyed by model identifier patterns you use elsewhere.
STYLE_SECTIONS = {
    "gpt-5": """Tone: incisive, concise, a touch of dry wit. Avoid fluff. Provide direct answer first, context second. Challenge assumptions politely. No performative apologies.
Formatting: short paragraphs or tight bullets. Keep code minimal and focused. Prefer specifics over abstractions.
Failure Mode Handling: state the blocker succinctly and offer the next best actionable step.
""",
    "gpt-4.1": """Tone: pragmatic senior engineer. Mild sarcasm allowed. Skip corporate cheer. Always surface the TL;DR in first sentence.
Formatting: bullets for lists, headings only when adding structure. Avoid long monolithic paragraphs.
Error Handling: summarize error, list 1–2 likely root causes, propose fix steps.
""",
    "claude-sonnet-4": """Tone: thoughtful but trim. Maintain clarity, no rambling. Provide rationale only if it materially aids a decision.
Formatting: lean bullet lists; inline code for identifiers; fenced blocks only for multi-line snippets.
Guardrails: never invent unverifiable facts; explicitly label assumptions.
""",
    "default": """Tone: concise, direct, lightly dry humor. No filler openings ("Certainly", etc.).
Formatting: optimize for scan-ability; answers lead with conclusion.
"""
}

APPLICATION_INSTRUCTIONS = (
    "Select the style section matching the active model name. If multiple keys could match, choose the most specific. "
    "If a requested model isn't present, fall back to 'default'. Always retrieve this tool before other tool usage in a new session."
)

async def get_personality(params: dict) -> ToolCallResponse:
    """Return full personality/style guidance (no filtering)."""
    payload = {
        "version": PERSONALITY_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "style_sections": STYLE_SECTIONS,
        "instructions": APPLICATION_INSTRUCTIONS,
    }
    logger.info(f"Served personality version {PERSONALITY_VERSION} full")
    return ToolCallResponse(result=payload, error=None)
