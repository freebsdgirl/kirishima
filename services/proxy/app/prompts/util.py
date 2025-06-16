"""
This module provides utilities for rendering prompts using Jinja2 templates.

Functions:
    render_prompt(mode: str, context: dict) -> str:
        Renders a Jinja2 template based on the specified mode and context.

Constants:
    TEMPLATE_DIR: str
        The directory path where the Jinja2 templates are stored.

Objects:
    env: jinja2.Environment
        The Jinja2 environment configured with a file system loader and autoescaping.
"""

from jinja2 import Environment, FileSystemLoader, select_autoescape
import os

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")


env = Environment(
    loader=FileSystemLoader(TEMPLATE_DIR),
    autoescape=select_autoescape()
)


def render_prompt(mode, context):
    if mode in ["nsfw", "work", "default", "tts"]:
        template = env.get_template(f"default.j2")
    elif mode == "guest":
        template = env.get_template(f"guest.j2")
    elif mode == "alignment":
        template = env.get_template(f"alignment.j2")

    return template.render(**context)
 