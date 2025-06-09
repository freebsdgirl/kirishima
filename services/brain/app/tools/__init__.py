from .update_divoom import update_divoom
from .memory_add import memory_add
from .memory_delete import memory_delete
from .memory_search import memory_search
from .memory_list import memory_list

TOOL_FUNCTIONS = {
    "update_divoom": update_divoom,
    "memory_add": memory_add,
    "memory_delete": memory_delete,
    "memory_search": memory_search,
    "memory_list": memory_list
}
