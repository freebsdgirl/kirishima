"""
This module defines Pydantic models for the MCP (Model Context Protocol) server functionality.

The Model Context Protocol is a standardized API layer that exposes Brain's tools and capabilities
to external agents (like GitHub Copilot, Claude, or custom LLMs) in a discoverable, type-safe manner.
This enables any agent to dynamically discover available tools, understand their parameters and return
types, and execute them with automatic dependency resolution.

Models include:
- Tool schema definitions for dynamic discovery and validation
- Request/response models for tool execution with context passing
- Dependency resolution support for complex tool chains
- Standardized error handling and success responses

The MCP server bridges the gap between Kirishima's internal Brain orchestration and external
AI agents, providing a clean abstraction layer that maintains tool autonomy while enabling
sophisticated agent-driven workflows.

Classes:
    MCPToolSchema: Schema definition for discoverable tools with parameters and return types
    MCPToolsResponse: Response model for tool discovery endpoint with full tool catalog
    MCPToolRequest: Request model for tool execution with parameters and optional context
    MCPToolResponse: Standardized response model for all tool executions with success/error handling
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class ToolAnnotation(BaseModel):
    title: str
    readOnlyHint: Optional[bool] = False
    destructiveHint: Optional[bool] = False
    idempotentHint: Optional[bool] = False
    openWorldHint: Optional[bool] = False

class Tool(BaseModel):
    name: str
    title: str
    description: str
    inputSchema: Dict[str, Any]
    outputSchema: Optional[Dict[str, Any]] = None
    annotations: ToolAnnotation

class ToolsListResponse(BaseModel):
    tools: List[Tool]

class ToolCallRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]

class ToolCallResponse(BaseModel):
    result: Optional[Any]
    error: Optional[str] = None
