"""
Enhanced prompt dispatcher that uses the centralized prompt system.

This module provides a dispatcher that can fall back to either the centralized
prompt system (from the private config repo) or the legacy local prompt modules.
"""

import importlib
from app.prompts.centralized_loader import load_proxy_prompt

from shared.log_config import get_logger
logger = get_logger(f"proxy.{__name__}")

def get_system_prompt(request, provider=None, mode=None):
    """
    Select and generate the appropriate system prompt based on provider and mode.
    
    Tries centralized prompts first, then falls back to legacy modules.
    
    Args:
        request: The request object (should have .mode, etc).
        provider: Provider string (e.g., 'openai', 'ollama').
        mode: Mode string (e.g., 'default', 'nsfw').
    Returns:
        str: The generated system prompt.
    """
    provider = provider or getattr(request, "provider", None)
    mode = mode or getattr(request, "mode", None) or "default"

    # Try centralized prompt system first
    try:
        logger.info(f"Attempting centralized prompt for {provider}-{mode}")
        result = load_proxy_prompt(provider, mode, request)
        logger.info(f"Successfully loaded centralized prompt for {provider}-{mode}")
        return result
    except FileNotFoundError as e:
        logger.info(f"Centralized prompt not found: {e}")
    except Exception as e:
        logger.error(f"Failed to load centralized prompt: {e}")
        import traceback
        logger.error(traceback.format_exc())

    # Fall back to legacy module system
    logger.debug(f"Falling back to legacy modules for {provider}-{mode}")
    
    tried_modules = []
    module_names = [
        f"app.prompts.{provider}-{mode}",
        f"app.prompts.{provider}-default",
        "app.prompts.openai-default",
    ]

    for module_name in module_names:
        try:
            tried_modules.append(module_name)
            logger.debug(f"Trying to import module: {module_name}")
            module = importlib.import_module(module_name)
            if hasattr(module, "build_prompt"):
                logger.debug(f"Successfully loaded module: {module_name}")
                return module.build_prompt(request)
        except ImportError as e:
            logger.debug(f"Module {module_name} not found: {e}")
            continue
        except Exception as e:
            logger.error(f"Error building prompt with module {module_name}: {e}")
            continue

    # If we get here, no prompt source worked
    error_msg = f"No prompt found for provider={provider}, mode={mode}. Tried centralized system and modules: {tried_modules}"
    logger.error(error_msg)
    raise RuntimeError(error_msg)
