# MCP Tool Development Guide

This guide covers how to add new tools to Kirishima's MCP (Model Context Protocol) server, making them available to external agents like GitHub Copilot, Claude, and other AI assistants.

## Overview

The MCP server in Brain exposes Kirishima's tools through standardized JSON-RPC endpoints, enabling any external agent to discover and execute tools dynamically. Tools are defined in a registry, implemented as Python functions, and automatically exposed via FastAPI routes.

## Current Architecture

- **Tool Registry**: `/app/config/mcp_tools.json` - JSON schema definitions
- **Tool Implementation**: `/app/services/mcp/` - Python tool functions
- **Tool Routing**: `/app/routes/mcp.py` - FastAPI endpoints
- **Models**: `shared/models/mcp.py` - Pydantic request/response models

## Adding a New Tool: Step-by-Step

### Step 1: Define Tool Schema

Add your tool definition to `/app/config/mcp_tools.json`:

```json
{
  "your_tool_name": {
    "description": "Brief description of what the tool does and when to use it",
    "depends_on": ["optional_dependency_tool"],
    "parameters": {
      "type": "object",
      "properties": {
        "required_param": {
          "type": "string",
          "description": "Description of this parameter"
        },
        "optional_param": {
          "type": "integer",
          "description": "Optional parameter with default",
          "default": 10
        }
      },
      "required": ["required_param"]
    },
    "returns": {
      "type": "object",
      "properties": {
        "status": {
          "type": "string",
          "description": "Operation status"
        },
        "result": {
          "type": "object",
          "description": "Tool-specific result data"
        }
      }
    }
  }
}
```

### Step 2: Implement Tool Function

Create your tool implementation in `/app/services/mcp/your_tool_name.py`:

```python
"""
Tool description and purpose.
"""

from shared.models.mcp import MCPToolResponse
from typing import Dict, Any
import httpx
import os

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")


async def your_tool_name(parameters: Dict[str, Any]) -> MCPToolResponse:
    """
    Main tool function that handles the business logic.
    
    Args:
        parameters: Dict containing validated parameters from the tool call
        
    Returns:
        MCPToolResponse with success/failure status and result/error data
    """
    try:
        # Extract parameters
        required_param = parameters.get("required_param")
        optional_param = parameters.get("optional_param", 10)
        
        # Validate required parameters
        if not required_param:
            return MCPToolResponse(
                success=False, 
                error="required_param is required"
            )
        
        # Implement your tool logic here
        # Example: calling another service
        service_port = os.getenv("SERVICE_PORT", 4200)
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f'http://service:{service_port}/endpoint',
                json={"param": required_param}
            )
            response.raise_for_status()
            result = response.json()
            
        return MCPToolResponse(success=True, result=result)
        
    except httpx.HTTPError as e:
        logger.error(f"HTTP error in {__name__}: {e}")
        return MCPToolResponse(
            success=False, 
            error=f"HTTP error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error in {__name__}: {e}")
        return MCPToolResponse(success=False, error=str(e))
```

### Step 3: Register Tool in Executor

Add your tool import and mapping in `/app/services/mcp/executor.py`:

```python
# Add to imports
from app.services.mcp.your_tool_name import your_tool_name

# Add to TOOL_FUNCTIONS mapping
TOOL_FUNCTIONS = {
    "memory": memory,
    "github_issue": github_issue,
    "your_tool_name": your_tool_name,  # Add this line
}
```

### Step 4: Add Route (Optional)

For tools that need dedicated endpoints, add a route in `/app/routes/mcp.py`:

```python
@router.post("/your_tool_name", response_model=MCPToolResponse)
async def mcp_your_tool_name(request: MCPToolRequest):
    """
    MCP endpoint for your tool functionality.
    """
    return await execute_tool_with_dependencies("your_tool_name", request.parameters)
```

### Step 5: Test Your Tool

1. **Start the Brain service**: Your tool is automatically available via the generic `/mcp/execute` endpoint
2. **Test tool discovery**: `GET /mcp/tools` should include your tool
3. **Test tool execution**:

```bash
curl -X POST http://localhost:4201/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "your_tool_name",
    "parameters": {
      "required_param": "test_value"
    }
  }'
```

## Tool Categories

### Persistent Tools

Tools that modify system state (create/update/delete operations):

- **Log to Ledger**: Yes - these operations should be tracked
- **Examples**: `memory` (create action), `github_issue` (create action)

### Ephemeral Tools

Tools that query or search without modifying state:

- **Log to Ledger**: No - avoid cluttering conversation history
- **Examples**: `memory` (search action), context lookups

## Advanced Features

### Dependencies

Tools can depend on other tools using the `depends_on` array:

```json
{
  "complex_tool": {
    "depends_on": ["memory", "github_issue"],
    "description": "Tool that needs memory and GitHub access"
  }
}
```

Dependencies are automatically resolved and executed in the correct order.

### Error Handling

Always return `MCPToolResponse` with proper error handling:

```python
# Success
return MCPToolResponse(success=True, result={"data": "value"})

# Error
return MCPToolResponse(success=False, error="Descriptive error message")
```

### Service Communication

Use the standard pattern for calling other Kirishima services:

```python
service_port = os.getenv("SERVICE_PORT", default_port)
async with httpx.AsyncClient(timeout=60) as client:
    response = await client.method(f'http://service:{service_port}/endpoint')
    response.raise_for_status()
    return response.json()
```

## Example: Simple Echo Tool

Here's a complete minimal example:

**1. Schema** (`/app/config/mcp_tools.json`):

```json
{
  "echo": {
    "description": "Simple echo tool that returns the input message",
    "depends_on": [],
    "parameters": {
      "type": "object",
      "properties": {
        "message": {
          "type": "string",
          "description": "Message to echo back"
        }
      },
      "required": ["message"]
    },
    "returns": {
      "type": "object",
      "properties": {
        "echo": {"type": "string"},
        "timestamp": {"type": "string"}
      }
    }
  }
}
```

**2. Implementation** (`/app/services/mcp/echo.py`):

```python
from shared.models.mcp import MCPToolResponse
from typing import Dict, Any
from datetime import datetime

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")


async def echo(parameters: Dict[str, Any]) -> MCPToolResponse:
    """Echo the input message with timestamp."""
    try:
        message = parameters.get("message")
        if not message:
            return MCPToolResponse(success=False, error="Message is required")
        
        result = {
            "echo": message,
            "timestamp": datetime.now().isoformat()
        }
        
        return MCPToolResponse(success=True, result=result)
        
    except Exception as e:
        logger.error(f"Error in echo tool: {e}")
        return MCPToolResponse(success=False, error=str(e))
```

**3. Registration** (add to `/app/services/mcp/executor.py`):

```python
from app.services.mcp.echo import echo

TOOL_FUNCTIONS = {
    # ... existing tools
    "echo": echo,
}
```

## Testing and Validation

### Local Testing

```bash
# Test tool discovery
curl http://localhost:4201/mcp/tools

# Test tool execution
curl -X POST http://localhost:4201/mcp/execute \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "echo", "parameters": {"message": "Hello World"}}'
```

### Dependency Validation

```bash
# Check all tool dependencies are valid
curl http://localhost:4201/mcp/validate
```

## Best Practices

1. **Parameter Validation**: Always validate required parameters and provide clear error messages
2. **Error Handling**: Use try/catch blocks and return meaningful error descriptions
3. **Logging**: Use the shared logging module for consistent log formatting
4. **Timeouts**: Set reasonable timeouts for HTTP requests (default 60s)
5. **Documentation**: Include clear descriptions in both JSON schema and function docstrings
6. **Idempotency**: Design tools to be safely re-executable when possible
7. **Resource Management**: Use async context managers for HTTP clients and file operations

## Current Available Tools

- **memory**: Comprehensive memory management (search, create, update, delete, list, get)
- **github_issue**: GitHub issue management (create, view, comment, close, list)

## Future Enhancements

- ✅ **Client Authentication**: Tools are filtered by client type via URL-based routing
- **Input Validation**: Automatic parameter validation using JSON Schema
- **Retry Logic**: Automatic retry for transient failures
- **Caching**: Response caching for expensive operations
- **Rate Limiting**: Per-client rate limiting for resource protection

## Client Types and Tool Access

The MCP server supports different client types with filtered tool access:

### Internal Clients (`/mcp/`)

- **Full tool access**: All tools available
- **Usage**: Internal Kirishima requests, admin operations
- **Tools**: `*` (all current and future tools)

### GitHub Copilot (`/mcp/copilot/`)

- **Curated tool access**: Safe, useful tools for code assistance
- **Usage**: GitHub Copilot integration
- **Tools**: `memory`, `github_issue`
- **Benefits**: Can create memories about code patterns, manage GitHub issues

### External Clients (`/mcp/external/`)

- **Limited tool access**: Read-only operations
- **Usage**: Generic external integrations
- **Tools**: `memory` (search only)

### Client Configuration

Tool access is controlled via `.kirishima/mcp_clients.json`:

```json
{
  "copilot": {
    "allowed_tools": ["memory", "github_issue"],
    "restricted_tools": ["system_admin"]
  }
}
```

## Testing Client-Specific Access

```bash
# Test internal tools (full access)
curl http://localhost:4201/mcp/tools

# Test Copilot tools (filtered)
curl http://localhost:4201/mcp/copilot/tools

# Test Copilot MCP protocol
curl -X POST http://localhost:4201/mcp/copilot/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
```

---

For questions or issues with MCP tool development, check the logs in the Brain service container or refer to the main documentation in `/docs/MCP_Planning.md`.
