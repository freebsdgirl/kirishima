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
    
    # If we have a tool registry, resolve dependencies first
    if tool_registry:
        try:
            # Create a proper ToolRegistry instance and DependencyResolver
            from app.services.mcp.registry import ToolRegistry
            from app.services.mcp.dependencies import DependencyResolver
            
            # Create registry instance with the provided tool_registry data
            registry = ToolRegistry()
            registry.registry = tool_registry  # Override with the provided data
            
            resolver = DependencyResolver(registry)
            execution_order = resolver.resolve_dependencies(tool_name)
            logger.debug(f"Dependency resolution for {tool_name}: {execution_order}")
            
            # Execute dependencies first (all except the last one, which is the target tool)
            for dep_tool in execution_order[:-1]:
                logger.info(f"Executing dependency: {dep_tool}")
                dep_result = await _execute_single_tool_direct(dep_tool, {})
                if not dep_result.success:
                    logger.error(f"Dependency {dep_tool} failed: {dep_result.error}")
                    return MCPToolResponse(
                        success=False, 
                        result=None, 
                        error=f"Dependency '{dep_tool}' failed: {dep_result.error}"
                    )
        except DependencyError as e:
            logger.error(f"Dependency resolution failed for {tool_name}: {e}")
            return MCPToolResponse(success=False, result=None, error=f"Dependency error: {str(e)}")
    
    # Execute the main tool
    return await _execute_single_tool_direct(tool_name, parameters)


async def _execute_single_tool_direct(tool_name: str, parameters: Dict[str, Any]) -> MCPToolResponse:
    """Execute a single tool directly without dependency resolution."""
    # Map tool names to module names (in case they differ)
    module_mapping = {
        "github_issue": "github_issue",
        "memory": "memory",
        "manage_prompt": "manage_prompt",
        "email": "email",
        "calendar": "calendar",
        "contacts": "contacts",
        "stickynotes": "stickynotes",
        "lists": "lists",
    "smarthome": "smarthome",
    "get_personality": "get_personality"
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
    
    # For now, just use direct execution - context support can be added later if needed
    return await _execute_single_tool_direct(tool_name, parameters)


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
