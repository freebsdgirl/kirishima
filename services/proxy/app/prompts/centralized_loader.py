"""
Proxy-specific prompt loader for centralized prompt system.

This module provides prompt loading functionality specifically for the proxy service,
avoiding shared module import issues in Docker containers.
"""

import os
import json
import logging
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

# Base path for prompts in Docker containers
PROMPTS_BASE_PATH = "/app/config/prompts"

class ProxyPromptLoader:
    """Handles loading and rendering of proxy prompts from the centralized prompt repository."""
    
    def __init__(self, base_path: str = PROMPTS_BASE_PATH):
        self.base_path = Path(base_path)
        self._jinja_env = None
    
    @property
    def jinja_env(self) -> Environment:
        """Lazy initialization of Jinja environment."""
        if self._jinja_env is None:
            self._jinja_env = Environment(
                loader=FileSystemLoader(str(self.base_path)),
                trim_blocks=True,
                lstrip_blocks=True
            )
        return self._jinja_env
    
    def load_proxy_prompt(self, provider: str, mode: str, request) -> str:
        """
        Load and render a proxy prompt using context data and templates.
        
        Args:
            provider: Provider name (e.g., 'openai', 'anthropic', 'ollama')
            mode: Mode name (e.g., 'default', 'work', 'boyfriend', 'nsfw')
            request: The request object containing timestamp, agent_prompt, etc.
            
        Returns:
            str: The rendered prompt text
            
        Raises:
            FileNotFoundError: If the context file or template doesn't exist
            Exception: If JSON parsing or template rendering fails
        """
        # Load context data
        context_file = f"proxy/contexts/{provider}-{mode}.json"
        context_path = self.base_path / context_file
        
        if not context_path.exists():
            raise FileNotFoundError(f"Proxy context not found: {context_file}")
        
        try:
            with open(context_path, 'r', encoding='utf-8') as f:
                context = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse context JSON {context_file}: {e}")
            raise
        
        # Add dynamic context from request
        context.update({
            "time": request.timestamp if hasattr(request, 'timestamp') else None,
            "summaries": getattr(request, 'summaries', ""),
            "agent_prompt": getattr(request, 'agent_prompt', None),
        })
        
        # Special handling for modes that need memories
        if hasattr(request, 'memories') and request.memories:
            # Handle memory string creation if needed
            if 'memories' not in context:
                memory_lines = []
                for memory in request.memories:
                    if hasattr(memory, 'content'):
                        memory_lines.append(memory.content)
                    else:
                        memory_lines.append(str(memory))
                context['memories'] = '\n'.join(memory_lines)
        
        # Special handling for guest mode
        if mode == 'guest' and hasattr(request, 'username'):
            context['username'] = request.username
            context['mode'] = getattr(request, 'mode', mode)
        
        # Get template name (default to 'default' if not specified)
        template_name = context.get('template', 'default')
        template_file = f"proxy/templates/{template_name}.j2"
        
        # Render template
        try:
            template = self.jinja_env.get_template(template_file)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Failed to render proxy template {template_file}: {e}")
            raise

# Global instance
_prompt_loader = ProxyPromptLoader()

def load_proxy_prompt(provider: str, mode: str, request) -> str:
    """
    Convenience function to load proxy prompts using the global ProxyPromptLoader instance.
    
    Args:
        provider: Provider name (e.g., 'openai', 'anthropic', 'ollama')
        mode: Mode name (e.g., 'default', 'work', 'boyfriend', 'nsfw')
        request: The request object containing timestamp, agent_prompt, etc.
        
    Returns:
        str: The rendered prompt text
    """
    return _prompt_loader.load_proxy_prompt(provider, mode, request)
