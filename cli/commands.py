from __future__ import annotations


def is_admin_command(text: str) -> bool:
    return text.startswith("/")
