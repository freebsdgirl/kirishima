"""
This module provides a dispatcher for selecting and generating system prompts based on the request mode.
It imports prompt-building functions for different modes ('guest', 'nsfw', 'work', 'default') and exposes
 a single function, `get_system_prompt`, which determines the appropriate prompt to use according to the
mode specified in the request object.
Functions:
    get_system_prompt(request): Returns a system prompt string generated for the specified request mode.
"""

import importlib


def get_system_prompt(request, provider=None, mode=None):
    """
    Select and generate the appropriate system prompt based on provider and mode.
    Args:
        request: The request object (should have .mode, etc).
        provider: Provider string (e.g., 'openai', 'ollama').
        mode: Mode string (e.g., 'default', 'nsfw').
    Returns:
        str: The generated system prompt.
    """
    provider = provider or getattr(request, "provider", None)
    mode = mode or getattr(request, "mode", None) or "default"

    tried_modules = []
    module_names = [
        f"app.prompts.{provider}-{mode}",
        f"app.prompts.{provider}-default",
        "app.prompts.openai-default",
    ]
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
            return module.build_prompt(request)
        except ModuleNotFoundError:
            tried_modules.append(module_name)
            continue
    raise Exception(f"No prompt template found for provider={provider}, mode={mode}. Tried: {tried_modules}")