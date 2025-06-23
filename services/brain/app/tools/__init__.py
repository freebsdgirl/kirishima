from .manage_prompt import manage_prompt
from .memory_add import memory_add
from .memory_delete import memory_delete
from .memory_search import memory_search
from .memory_list import memory_list
from .tts import tts
from .update_divoom import update_divoom
from .github_issue import github_issue

TOOL_FUNCTIONS = {
    "manage_prompt": manage_prompt,
    "memory_add": memory_add,
    "memory_delete": memory_delete,
    "memory_search": memory_search,
    "memory_list": memory_list,
    "tts": tts,
    "update_divoom": update_divoom,
    "github_issue": github_issue
}
