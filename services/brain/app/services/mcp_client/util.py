"""
Utility: Convert MCP tool list to OpenAI tool/function schema
"""
def mcp_tools_to_openai(tools):
    """
    Convert MCP tool list (from list_tools) to OpenAI-compatible tool/function list.
    Args:
        tools: List of MCP tool dicts (output from MCPClient.list_tools())
    Returns:
        List of OpenAI tool/function dicts
    """
    result = []
    for tool in tools:
        entry = {
            "type": "function",
            "function": {
                "name": tool.get("name"),
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema", {})
            }
        }
        result.append(entry)
    return result

# Example usage:
# tools = await client.list_tools()
# openai_tools = mcp_tools_to_openai(tools)
