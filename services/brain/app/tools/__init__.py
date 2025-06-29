from .manage_prompt import manage_prompt
from .memory import memory
from .tts import tts
from .update_divoom import update_divoom
from .github_issue import github_issue
from .smarthome import smarthome
from .stickynotes import stickynotes

TOOL_FUNCTIONS = {
    "manage_prompt": manage_prompt,
    "memory": memory,
    "tts": tts,
    "update_divoom": update_divoom,
    "github_issue": github_issue,
    "smarthome": smarthome,
    "stickynotes": stickynotes
}
