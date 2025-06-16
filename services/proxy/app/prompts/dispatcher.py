"""
This module provides a dispatcher for selecting and generating system prompts based on the request mode.
It imports prompt-building functions for different modes ('guest', 'nsfw', 'work', 'default') and exposes
a single function, `get_system_prompt`, which determines the appropriate prompt to use according to the
mode specified in the request object.
Functions:
    get_system_prompt(request): Returns a system prompt string generated for the specified request mode.
"""

import importlib

# Registry of available prompt builders: (provider, mode) -> module_name
PROMPT_REGISTRY = {
    ("openai", "default"): "app.prompts.openai-default",
    ("ollama", "default"): "app.prompts.ollama-default",
    ("openai", "tts"): "app.prompts.openai-tts",
    ("ollama", "nsfw"): "app.prompts.ollama-nsfw",
    ("openai", "work"): "app.prompts.work",
    ("ollama", "work"): "app.prompts.work",
    ("openai", "guest"): "app.prompts.guest",
    ("ollama", "guest"): "app.prompts.guest",
    # Add more as needed
}

# Fallbacks
FALLBACKS = [
    ("{provider}", "default"),
    (None, "default"),
]


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
    # Allow explicit override, else infer from request
    provider = provider or getattr(request, "provider", None)
    mode = mode or getattr(request, "mode", None) or "default"

    # Try (provider, mode) first
    key = (provider, mode)
    module_name = PROMPT_REGISTRY.get(key)
    if not module_name:
        # Try fallbacks
        for prov, mod in FALLBACKS:
            k = ((provider if prov == "{provider}" else prov), mod)
            module_name = PROMPT_REGISTRY.get(k)
            if module_name:
                break
    if not module_name:
        raise Exception(f"No prompt template found for provider={provider}, mode={mode}")
    module = importlib.import_module(module_name)
    return module.build_prompt(request)