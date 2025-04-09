"""
This module provides a function to dynamically select and return a prompt builder 
based on the specified mode and optional memories.
Functions:
    get_prompt_builder(mode: Optional[str], memories: Optional[list]) -> Callable:
        Dynamically selects and returns a prompt builder function based on the 
        provided mode and memories. Imports the appropriate module for the 
        specified mode and returns the corresponding `build_prompt` function.
"""

from typing import Optional


def get_prompt_builder(mode: Optional[str], memories: Optional[list]):
    """
    Dynamically select and return a prompt builder function based on the provided mode and memories.
    
    Args:
        mode (Optional[str]): The mode determining which prompt builder to use.
        memories (Optional[list]): Optional list of memories to influence prompt builder selection.
            If memories are included, this signifies the platform is not in guest mode.
            If memories are None, the platform is in guest mode.
    
    Returns:
        Callable: A prompt builder function corresponding to the specified mode or default/guest mode.
    """
    if mode and memories:
        if mode == "nsfw":
            from app.prompts.nsfw.generate import build_prompt

        elif mode == "work":
            from app.prompts.work.generate import build_prompt

        else:
            from app.prompts.default.generate import build_prompt

    else:
        from app.prompts.guest.generate import build_prompt

    return build_prompt
