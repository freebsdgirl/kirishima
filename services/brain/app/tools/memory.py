"""
This consoldiates all the memory-related tools into a single tool with multiple actions.

"""

from app.memories.search import memory_search
from app.memories.add import memory_add
from app.memories.delete import memory_delete
from app.memories.list import memory_list

def memory(action: str, **kwargs):
    """
    Consolidated memory tool that routes to specific actions based on the action parameter.
    
    :param action: The action to perform (e.g., 'search', 'add', 'delete', 'list').
    :param kwargs: Additional parameters required for the specific action.
    :return: Result of the specified memory action.
    """
    if action == "search":
        return memory_search(**kwargs, min_keywords=2)
    elif action == "add":
        return memory_add(**kwargs)
    elif action == "delete":
        return memory_delete(**kwargs)
    elif action == "list":
        return memory_list(**kwargs)
    else:
        raise ValueError(f"Unknown action: {action}")
