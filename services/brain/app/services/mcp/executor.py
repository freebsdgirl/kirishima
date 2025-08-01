"""
Tool execution service with dependency resolution.
"""

from typing import Dict, Any, List
from shared.models.mcp import MCPToolResponse
from app.services.mcp.dependencies import resolve_dependencies, DependencyError
from app.services.mcp.registry import is_tool_available

from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")


async def execute_tool_with_dependencies(tool_name: str, parameters: dict, tool_registry: dict = None) -> MCPToolResponse:
    """Execute a tool with automatic dependency resolution."""
    logger.info(f"Executing tool: {tool_name}")
    
    # Map tool names to module names (in case they differ)
    module_mapping = {
        "github_issue": "github_issue",
        "memory": "memory",
        "manage_prompt": "manage_prompt"
    }
    
    # Get the module name
    module_name = module_mapping.get(tool_name, tool_name)
    
    try:
        # Dynamic import based on tool name
        module_path = f"app.services.mcp.{module_name}"
        module = __import__(module_path, fromlist=[module_name])
        
        # For memory tool, the function is named 'memory', for others it matches the tool name
        function_name = "memory" if tool_name == "memory" else tool_name
        tool_function = getattr(module, function_name)
        
        # Call the async function
        return await tool_function(parameters)
        
    except (ImportError, AttributeError):
        return MCPToolResponse(success=False, result=None, error=f"Tool '{tool_name}' not implemented")
    except Exception as e:
        return MCPToolResponse(success=False, result=None, error=str(e))


async def _execute_single_tool(tool_name: str, parameters: Dict[str, Any], context: Dict[str, Any] = None) -> MCPToolResponse:
    """Execute a single tool."""
    if not is_tool_available(tool_name):
        return MCPToolResponse(success=False, result=None, error=f"Tool '{tool_name}' not found")
    
    try:
        # Dynamic import based on tool name
        module_name = f"app.services.mcp.{tool_name}"
        module = __import__(module_name, fromlist=[tool_name])
        tool_function = getattr(module, tool_name)
        
        # Call tool with context if it accepts it
        import inspect
        sig = inspect.signature(tool_function)
        if 'context' in sig.parameters:
            return await tool_function(parameters, context)
        else:
            return await tool_function(parameters)
            
    except (ImportError, AttributeError):
        return MCPToolResponse(success=False, result=None, error=f"Tool '{tool_name}' not implemented")
    except Exception as e:
        return MCPToolResponse(success=False, result=None, error=str(e))


async def execute_multiple_tools(tool_requests: List[Dict[str, Any]]) -> List[MCPToolResponse]:
    """
    Execute multiple tools with dependency resolution.
    
    Args:
        tool_requests: List of dicts with 'tool_name' and 'parameters' keys
    
    Returns:
        List of MCPToolResponse objects
    """
    results = []
    
    for request in tool_requests:
        tool_name = request.get("tool_name")
        parameters = request.get("parameters", {})
        
        if not tool_name:
            results.append(MCPToolResponse(success=False, error="Missing tool_name"))
            continue
        
        result = await execute_tool_with_dependencies(tool_name, parameters)
        results.append(result)
    
    return results
