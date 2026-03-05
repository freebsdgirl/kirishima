from __future__ import annotations

from cli.client import ChatUsage


def render_assistant_reply(text: str, duration_s: float, usage: ChatUsage, model: str) -> None:
    print(f"kirishima> {text or '[empty response]'}")
    print(
        "meta> "
        f"{duration_s:.2f}s"
        f" | model={model}"
        f" | prompt={_or_dash(usage.prompt_tokens)}"
        f" completion={_or_dash(usage.completion_tokens)}"
        f" total={_or_dash(usage.total_tokens)}"
    )


def render_error(message: str) -> None:
    print(f"error> {message}")


def render_help() -> None:
    print("Local commands:")
    print("  /help         Show this help")
    print("  /mode         Show current mode")
    print("  /mode <name>  Set mode for subsequent chat requests")
    print("  /clear        Clear terminal")
    print("  /exit         Exit CLI")
    print("Input shortcuts:")
    print("  Enter         Send message")
    print("  Shift+Enter   Insert newline (prompt_toolkit)")
    print("  Alt+Enter     Insert newline fallback (prompt_toolkit)")
    print("  /...          Admin commands not implemented yet")


def _or_dash(value: int | None) -> str:
    return "-" if value is None else str(value)
