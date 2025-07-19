"""
Centralized prompt loading utility for the Kirishima system.

This module provides a standardized way to load prompts from the private config repository,
supporting both simple text files and Jinja templates with variable substitution.

The prompt files are stored in /app/config/prompts/ (mounted from the private repo)
with the following structure:
- /app/config/prompts/{service}/{module}/{prompt_name}.txt (simple text)
- /app/config/prompts/{service}/{module}/{prompt_name}.j2 (Jinja template)

For proxy service, additional support for context-driven prompts:
- /app/config/prompts/proxy/contexts/{provider}-{mode}.json (context data)
- /app/config/prompts/proxy/templates/{template_name}.j2 (Jinja templates)

Usage:
    from shared.prompt_loader import load_prompt
    
    # Simple text prompt
    prompt = load_prompt("ledger", "memory", "scan")
    
    # Jinja template with variables
    prompt = load_prompt("ledger", "summary", "periodic", 
                        conversation_str=conversation, max_tokens=256)
    
    # Proxy service context-driven prompt
    prompt = load_proxy_prompt("openai", "default", request)
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from jinja2 import Template, FileSystemLoader, Environment

logger = logging.getLogger(__name__)

# Base path for prompts in Docker containers
PROMPTS_BASE_PATH = "/app/config/prompts"

class PromptLoader:
    """Handles loading and rendering of prompts from the centralized prompt repository."""
    
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
    
    def load_prompt(self, service: str, module: str, prompt_name: str, **kwargs) -> str:
        """
        Load and render a prompt from the centralized prompt repository.
        
        Args:
            service: Service name (e.g., 'ledger', 'brain')
            module: Module name (e.g., 'memory', 'summary')
            prompt_name: Prompt name (e.g., 'scan', 'periodic')
            **kwargs: Variables to substitute in Jinja templates
            
        Returns:
            str: The rendered prompt text
            
        Raises:
            FileNotFoundError: If the prompt file doesn't exist
            Exception: If template rendering fails
        """
        # Try Jinja template first, then fallback to plain text
        template_path = f"{service}/{module}/{prompt_name}.j2"
        text_path = f"{service}/{module}/{prompt_name}.txt"
        
        # Check for Jinja template
        full_template_path = self.base_path / template_path
        if full_template_path.exists():
            logger.debug(f"Loading Jinja template: {template_path}")
            try:
                template = self.jinja_env.get_template(template_path)
                return template.render(**kwargs)
            except Exception as e:
                logger.error(f"Failed to render template {template_path}: {e}")
                raise
        
        # Check for plain text file
        full_text_path = self.base_path / text_path
        if full_text_path.exists():
            logger.debug(f"Loading text prompt: {text_path}")
            if kwargs:
                logger.warning(f"Variables provided for text prompt {text_path}, but text prompts don't support variables")
            with open(full_text_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        
        # Neither found
        raise FileNotFoundError(f"Prompt not found: {service}/{module}/{prompt_name} (tried .j2 and .txt)")

    def load_proxy_prompt(self, provider: str, mode: str, request) -> str:
        """
        Load and render a proxy prompt using context data and templates.
        
        This method handles the proxy service's more complex prompt system that
        combines JSON context files with Jinja templates.
        
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
_prompt_loader = PromptLoader()

def load_prompt(service: str, module: str, prompt_name: str, **kwargs) -> str:
    """
    Convenience function to load prompts using the global PromptLoader instance.
    
    Args:
        service: Service name (e.g., 'ledger', 'brain')
        module: Module name (e.g., 'memory', 'summary') 
        prompt_name: Prompt name (e.g., 'scan', 'periodic')
        **kwargs: Variables to substitute in Jinja templates
        
    Returns:
        str: The rendered prompt text
    """
    return _prompt_loader.load_prompt(service, module, prompt_name, **kwargs)

def load_proxy_prompt(provider: str, mode: str, request) -> str:
    """
    Convenience function to load proxy prompts using the global PromptLoader instance.
    
    Args:
        provider: Provider name (e.g., 'openai', 'anthropic', 'ollama')
        mode: Mode name (e.g., 'default', 'work', 'boyfriend', 'nsfw')
        request: The request object containing timestamp, agent_prompt, etc.
        
    Returns:
        str: The rendered prompt text
    """
    return _prompt_loader.load_proxy_prompt(provider, mode, request)

def list_prompts(service: Optional[str] = None, module: Optional[str] = None) -> Dict[str, Any]:
    """
    List available prompts in the repository.
    
    Args:
        service: Optional service filter
        module: Optional module filter (requires service)
        
    Returns:
        Dict containing the prompt structure
    """
    base_path = Path(PROMPTS_BASE_PATH)
    if not base_path.exists():
        return {}
    
    result = {}
    
    # If service specified, filter to that service
    if service:
        service_path = base_path / service
        if not service_path.exists():
            return {}
        services = [service]
    else:
        services = [d.name for d in base_path.iterdir() if d.is_dir()]
    
    for svc in services:
        service_path = base_path / svc
        result[svc] = {}
        
        # If module specified, filter to that module
        if module:
            if service:
                module_path = service_path / module
                if not module_path.exists():
                    continue
                modules = [module]
            else:
                continue  # Can't filter by module without service
        else:
            modules = [d.name for d in service_path.iterdir() if d.is_dir()]
        
        for mod in modules:
            module_path = service_path / mod
            result[svc][mod] = []
            
            for file_path in module_path.iterdir():
                if file_path.is_file() and file_path.suffix in ['.txt', '.j2']:
                    prompt_name = file_path.stem
                    prompt_type = 'template' if file_path.suffix == '.j2' else 'text'
                    result[svc][mod].append({
                        'name': prompt_name,
                        'type': prompt_type,
                        'path': str(file_path.relative_to(base_path))
                    })
    
    return result
