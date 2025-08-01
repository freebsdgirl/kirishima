"""
Dependency resolution service for MCP tools.
Handles calculating execution order and resolving dependencies.
"""

from typing import List, Dict, Any, Set


class DependencyError(Exception):
    """Raised when there are dependency resolution issues."""
    pass


class DependencyResolver:
    """Handles dependency resolution for MCP tools."""
    
    def __init__(self, tool_registry):
        """Initialize with a tool registry instance."""
        self.tool_registry = tool_registry
    
    def resolve_dependencies(self, tool_name: str, visited: Set[str] = None) -> List[str]:
        """
        Resolve dependencies for a tool and return execution order.
        
        Args:
            tool_name: The tool to resolve dependencies for
            visited: Set of already visited tools (for cycle detection)
        
        Returns:
            List of tool names in execution order (dependencies first)
        
        Raises:
            DependencyError: If circular dependencies or missing tools are found
        """
        if visited is None:
            visited = set()
        
        if tool_name in visited:
            raise DependencyError(f"Circular dependency detected involving tool: {tool_name}")
        
        tool_info = self.tool_registry.get_tool_info(tool_name)
        if not tool_info:
            raise DependencyError(f"Tool not found: {tool_name}")
        
        visited.add(tool_name)
        execution_order = []
        
        # Get dependencies for this tool
        dependencies = tool_info.get("depends_on", [])
        
        # Recursively resolve dependencies
        for dep_tool in dependencies:
            dep_order = self.resolve_dependencies(dep_tool, visited.copy())
            # Add dependencies that aren't already in our execution order
            for dep in dep_order:
                if dep not in execution_order:
                    execution_order.append(dep)
        
        # Add the current tool if it's not already in the execution order
        if tool_name not in execution_order:
            execution_order.append(tool_name)
        
        return execution_order
    
    def get_execution_plan(self, tool_name: str) -> List[str]:
        """
        Get execution plan for a single tool, resolving all dependencies.
        
        Args:
            tool_name: Tool to execute
        
        Returns:
            Ordered list of tools to execute (dependencies resolved)
        
        Raises:
            DependencyError: If dependency resolution fails
        """
        return self.resolve_dependencies(tool_name)
    
    def validate_all_dependencies(self) -> Dict[str, Any]:
        """
        Validate all tool dependencies in the registry.
        
        Returns:
            Dict containing validation results with any errors found
        """
        from app.services.mcp.registry import TOOL_REGISTRY
        
        results = {
            "valid": True,
            "errors": [],
            "warnings": []
        }
        
        for tool_name in TOOL_REGISTRY.keys():
            try:
                self.resolve_dependencies(tool_name)
            except DependencyError as e:
                results["valid"] = False
                results["errors"].append(f"{tool_name}: {str(e)}")
        
        return results


# Legacy functions for backward compatibility
def resolve_dependencies(tool_name: str, visited: Set[str] = None) -> List[str]:
    """Legacy function - use DependencyResolver class instead."""
    from app.services.mcp.registry import ToolRegistry
    registry = ToolRegistry()
    resolver = DependencyResolver(registry)
    return resolver.resolve_dependencies(tool_name, visited)


def validate_all_dependencies() -> Dict[str, Any]:
    """Legacy function - use DependencyResolver class instead."""
    from app.services.mcp.registry import ToolRegistry
    registry = ToolRegistry()
    resolver = DependencyResolver(registry)
    return resolver.validate_all_dependencies()


def get_execution_plan(tool_name: str) -> List[str]:
    """Legacy function - use DependencyResolver class instead."""
    from app.services.mcp.registry import ToolRegistry
    registry = ToolRegistry()
    resolver = DependencyResolver(registry)
    return resolver.get_execution_plan(tool_name)
