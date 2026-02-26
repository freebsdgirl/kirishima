"""Tool decorator and response model for the Kirishima tool system.

Every tool module uses the @tool decorator to declare metadata inline.
The decorator attaches metadata as fn._tool_meta — the registry discovers
these at import time. No JSON files, no manual registration.

Usage:
    from app.tools.base import tool, ToolResponse

    @tool(
        name="my_tool",
        description="Does a thing",
        parameters={"type": "object", "properties": {...}, "required": [...]},
        persistent=True,
        always=False,
        clients=["internal"],
    )
    async def my_tool(parameters: dict) -> ToolResponse:
        return ToolResponse(result={"status": "ok"})
"""

from typing import Any, List, Optional
from pydantic import BaseModel


class ToolResponse(BaseModel):
    """Unified response model for all tools.

    Replaces both ToolCallResponse and the defunct MCPToolResponse.
    Every tool returns this — no exceptions.
    """
    result: Optional[Any] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


class ToolMeta(BaseModel):
    """Metadata attached to a tool function by the @tool decorator."""
    name: str
    description: str
    parameters: dict  # JSON Schema (OpenAI function calling format)
    persistent: bool = False  # whether tool calls are logged to ledger
    always: bool = False  # always included in LLM calls vs routed
    clients: List[str] = ["internal"]  # who can call this tool
    service: Optional[str] = None  # which microservice it depends on (informational)
    guidance: Optional[str] = None  # extra context injected into system prompt when tool is available


def tool(
    name: str,
    description: str,
    parameters: dict,
    persistent: bool = False,
    always: bool = False,
    clients: Optional[List[str]] = None,
    service: Optional[str] = None,
    guidance: Optional[str] = None,
):
    """Decorator that attaches tool metadata to an async function.

    The decorated function's signature must be:
        async def tool_name(parameters: dict) -> ToolResponse

    Metadata is stored as fn._tool_meta (a ToolMeta instance).
    The auto-discovery registry in __init__.py picks this up at import time.
    """
    if clients is None:
        clients = ["internal"]

    meta = ToolMeta(
        name=name,
        description=description,
        parameters=parameters,
        persistent=persistent,
        always=always,
        clients=clients,
        service=service,
        guidance=guidance,
    )

    def decorator(fn):
        fn._tool_meta = meta
        return fn

    return decorator
