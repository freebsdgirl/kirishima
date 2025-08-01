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


class MCPToolSchema(BaseModel):
    """
    Schema definition for an MCP tool, used for dynamic tool discovery and validation.
    
    This model defines the complete interface contract for a tool, including its name,
    description, parameter schema (JSON Schema format), and return type schema.
    Agents use this information to understand what tools are available, what inputs
    they require, and what outputs they provide.
    
    The parameter and return schemas follow JSON Schema specification, enabling
    rich validation, type checking, and automatic UI generation in agent interfaces.
    
    Attributes:
        name (str): Unique tool identifier, used for tool execution routing
        description (str): Human-readable description of tool functionality and use cases
        parameters (Dict[str, Any]): JSON Schema defining required and optional parameters
        returns (Dict[str, Any]): JSON Schema defining the structure of tool return values
    """
    name: str = Field(
        ..., 
        description="Unique tool identifier used for execution routing and discovery",
        min_length=1,
        max_length=100,
        pattern="^[a-z][a-z0-9_]*$"
    )
    description: str = Field(
        ..., 
        description="Human-readable description of tool functionality, use cases, and behavior",
        min_length=10,
        max_length=500
    )
    parameters: Dict[str, Any] = Field(
        ..., 
        description="JSON Schema object defining tool parameters, types, validation rules, and required fields"
    )
    returns: Dict[str, Any] = Field(
        ..., 
        description="JSON Schema object defining the structure and types of tool return values"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "name": "memory_search",
                "description": "Search for relevant memories based on keywords, categories, or contextual similarity using the ledger service",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query or keywords to find relevant memories"
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results to return",
                            "default": 10,
                            "minimum": 1,
                            "maximum": 100
                        },
                        "category": {
                            "type": "string",
                            "description": "Optional category filter for memory search",
                            "enum": ["personal", "work", "technical", "creative"]
                        }
                    },
                    "required": ["query"]
                },
                "returns": {
                    "type": "object",
                    "properties": {
                        "memories": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},
                                    "content": {"type": "string"},
                                    "score": {"type": "number"},
                                    "created_at": {"type": "string"}
                                }
                            }
                        },
                        "count": {
                            "type": "integer",
                            "description": "Total number of memories found"
                        }
                    }
                }
            }
        }
    }


class MCPToolsResponse(BaseModel):
    """
    Response model for the tool discovery endpoint, containing the complete catalog of available tools.
    
    This model wraps the list of available tools returned by the GET /mcp/tools endpoint.
    Agents use this response to understand what tools are available in the current Brain
    instance, enabling dynamic capability discovery and adaptive agent behavior.
    
    The tools list includes full schema information for each tool, allowing agents to
    validate inputs, understand outputs, and generate appropriate tool calls.
    
    Attributes:
        tools (List[MCPToolSchema]): Complete list of available tools with their schemas
    """
    tools: List[MCPToolSchema] = Field(
        ..., 
        description="Complete list of available tools with their parameter and return schemas",
        min_items=0
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "tools": [
                    {
                        "name": "memory_search",
                        "description": "Search for relevant memories based on keywords or context",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string", "description": "Search query"},
                                "limit": {"type": "integer", "default": 10}
                            },
                            "required": ["query"]
                        },
                        "returns": {
                            "type": "object",
                            "properties": {
                                "memories": {"type": "array"},
                                "count": {"type": "integer"}
                            }
                        }
                    },
                    {
                        "name": "add_stickynote",
                        "description": "Create a persistent, context-aware reminder",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string", "description": "Reminder content"},
                                "priority": {"type": "string", "enum": ["low", "medium", "high"]}
                            },
                            "required": ["content"]
                        },
                        "returns": {
                            "type": "object",
                            "properties": {
                                "note_id": {"type": "string"},
                                "status": {"type": "string"}
                            }
                        }
                    }
                ]
            }
        }
    }


class MCPToolRequest(BaseModel):
    """
    Request model for tool execution, containing tool identification, parameters, and optional context.
    
    This model standardizes how agents request tool execution across all MCP endpoints.
    It includes the tool name for routing, parameters that match the tool's schema,
    and optional context that can be passed between dependent tools.
    
    The context field enables sophisticated tool chaining where the output of one tool
    becomes available as input context to dependent tools, supporting complex workflows
    like retrieving personality context before creating GitHub issues.
    
    Attributes:
        tool_name (str): Name of the tool to execute, must match an available tool
        parameters (Dict[str, Any]): Tool parameters matching the tool's parameter schema
        context (Optional[Dict[str, Any]]): Optional context from previous tool executions
    """
    tool_name: str = Field(
        ..., 
        description="Name of the tool to execute, must match an available tool in the registry",
        min_length=1,
        max_length=100,
        pattern="^[a-z][a-z0-9_]*$"
    )
    parameters: Dict[str, Any] = Field(
        ..., 
        description="Tool parameters as key-value pairs, must conform to the tool's parameter schema"
    )
    context: Optional[Dict[str, Any]] = Field(
        None, 
        description="Optional context data from previous tool executions, used for tool chaining and dependency resolution"
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "tool_name": "create_github_issue",
                "parameters": {
                    "title": "Fix memory search timeout issue",
                    "body": "The memory search tool is timing out when processing large queries. Need to implement pagination and optimize the search algorithm.",
                    "labels": ["bug", "memory", "performance"]
                },
                "context": {
                    "personality_context": {
                        "voice": "technical",
                        "tone": "professional",
                        "style": "concise"
                    },
                    "previous_tool_results": {
                        "memory_search": {
                            "found_related_issues": 3,
                            "search_time_ms": 5420
                        }
                    }
                }
            }
        }
    }


class MCPToolResponse(BaseModel):
    """
    Standardized response model for all tool executions, providing consistent success/error handling.
    
    This model wraps the results of tool execution in a standardized format that agents
    can reliably parse and handle. It includes a success flag, the actual tool result,
    and optional error information for failed executions.
    
    The result field can contain any JSON-serializable data structure as defined by
    the tool's return schema. The error field provides detailed error information
    when tools fail, enabling agents to handle errors gracefully and provide
    meaningful feedback to users.
    
    Attributes:
        success (bool): Whether the tool execution completed successfully
        result (Any): Tool execution result, structure defined by tool's return schema
        error (Optional[str]): Error message if execution failed, None if successful
    """
    success: bool = Field(
        ..., 
        description="Whether the tool execution completed successfully without errors"
    )
    result: Any = Field(
        ..., 
        description="Tool execution result, structure defined by the tool's return schema in MCPToolSchema"
    )
    error: Optional[str] = Field(
        None, 
        description="Detailed error message if execution failed, None if successful"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "description": "Successful tool execution",
                    "value": {
                        "success": True,
                        "result": {
                            "memories": [
                                {
                                    "id": "mem_123",
                                    "content": "User prefers technical documentation with code examples",
                                    "score": 0.89,
                                    "created_at": "2025-01-15T10:30:00Z"
                                }
                            ],
                            "count": 1
                        },
                        "error": None
                    }
                },
                {
                    "description": "Failed tool execution",
                    "value": {
                        "success": False,
                        "result": None,
                        "error": "Tool 'memory_search' failed: Database connection timeout after 30 seconds"
                    }
                },
                {
                    "description": "Tool with dependency execution",
                    "value": {
                        "success": True,
                        "result": {
                            "issue_number": 42,
                            "url": "https://github.com/freebsdgirl/kirishima/issues/42",
                            "status": "created",
                            "title": "Fix memory search timeout issue",
                            "personality_applied": True
                        },
                        "error": None
                    }
                }
            ]
        }
    }
