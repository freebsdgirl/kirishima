import json
from typing import List
from shared.models.memory import MemoryEntryFull


def _create_memory_str(memories: List[MemoryEntryFull]) -> str:
    """
    Converts a list of memory entries into a single string representation.
    
    Args:
        memories (List[MemoryEntryFull]): A list of memory entries to be converted.
    
    Returns:
        str: A single string with memory entries joined by newlines, in reverse order.
    """
    return "\n".join([f" - {m.memory}" for m in reversed(memories)])


def _build_multiturn_prompt(messages: list, system_prompt: str, provider: str = None) -> str:
    """
    Builds a multi-turn prompt for a language model using the specified chat messages and system prompt.
    Provider-specific formatting is applied (e.g., OpenAI vs. Ollama/instruct style).
    Args:
        messages (list): The sequence of chat messages (dicts) to be formatted.
        system_prompt (str): The initial system-level instruction for the model.
        provider (str, optional): The provider (e.g., 'openai', 'ollama').
    Returns:
        str: A formatted multi-turn prompt compatible with the provider's requirements.
    """
    if provider == "openai":
        # For OpenAI, the prompt is handled via the messages list, so just return system_prompt for logging/debug
        return system_prompt
    # Default: Ollama/instruct style
    prompt_header = f"[INST] <<SYS>>{system_prompt}<</SYS>> [/INST]\n\n"
    prompt = prompt_header
    for m in messages:
        if m["role"] == "system":
            prompt += f"[INST] <<SYS>>{m['content']}<</SYS>> [/INST]\n"
        elif m["role"] == "user":
            prompt += f"[INST] {m['content']} [/INST]"
        elif m["role"] == "assistant":
            prompt += f" {m['content']}\n"
    return prompt


def _resolve_model_provider_options(mode: str):
    """
    Given a mode string, return (provider, model, options) for the LLM.
    Looks up the mode in the loaded config. If not found, falls back to 'default'.
    Returns:
        provider (str): e.g. 'openai', 'ollama'
        model (str): actual model name for the provider
        options (dict): provider-specific options (temperature, max_tokens, etc.)
    Raises:
        ValueError: If provider is missing from the config for the mode.
    """
    with open('/app/config/config.json') as f:
        _config = json.load(f)
    llm_modes = _config.get("llm", {}).get("mode", {})
    mode_config = llm_modes.get(mode) or llm_modes.get("default")
    if not mode_config:
        raise ValueError(f"No config found for mode '{mode}' and no default mode present.")
    provider = mode_config.get("provider")
    if not provider:
        raise ValueError(f"No provider specified for mode '{mode}'. Please specify a provider in config.")
    model = mode_config.get("model")
    options = mode_config.get("options", {})
    return provider, model, options