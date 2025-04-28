"""
This module provides a dispatcher for selecting and generating system prompts based on the request mode.
It imports prompt-building functions for different modes ('guest', 'nsfw', 'work', 'default') and exposes
a single function, `get_system_prompt`, which determines the appropriate prompt to use according to the
mode specified in the request object.
Functions:
    get_system_prompt(request): Returns a system prompt string generated for the specified request mode.
"""

from app.prompts.guest import build_prompt as guest_prompt
from app.prompts.nsfw import build_prompt as nsfw_prompt
from app.prompts.work import build_prompt as work_prompt
from app.prompts.default import build_prompt as default_prompt


def get_system_prompt(request):
    """
    Determine and generate the appropriate system prompt based on the request mode.
    
    Selects a system prompt generation function based on the mode attribute of the request.
    Supports 'nsfw', 'work', 'default', and fallback 'guest' modes.
    
    Args:
        request: The request object containing the mode attribute.
    
    Returns:
        str: The generated system prompt corresponding to the specified mode.
    """
    mode = getattr(request, "mode", None) or "guest"
    if mode == "nsfw":
        return nsfw_prompt(request)
    elif mode == "work":
        return work_prompt(request)
    elif mode == "default":
        return default_prompt(request)
    else:
        return guest_prompt(request)