from .manage_prompt import manage_prompt
from .memory_add import memory_add
from .memory_delete import memory_delete
from .memory_search import memory_search
from .memory_list import memory_list
from .update_divoom import update_divoom

TOOL_FUNCTIONS = {
    "manage_prompt": manage_prompt,
    "memory_add": memory_add,
    "memory_delete": memory_delete,
    "memory_search": memory_search,
    "memory_list": memory_list,
    "update_divoom": update_divoom
}
