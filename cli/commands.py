from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedCommand:
    kind: str
    name: str
    method: str | None = None
    params: dict[str, object] | None = None


def is_admin_command(text: str) -> bool:
    return text.startswith("/")


def parse_command(text: str) -> ParsedCommand:
    message = text.strip()
    if not message.startswith("/"):
        raise ValueError("Commands must start with '/'.")

    if message == "/help":
        return ParsedCommand(kind="local", name="help")
    if message == "/clear":
        return ParsedCommand(kind="local", name="clear")
    if message == "/exit":
        return ParsedCommand(kind="local", name="exit")
    if message == "/mode" or message.startswith("/mode "):
        return ParsedCommand(kind="local", name="mode")
    if message == "/history" or message.startswith("/history "):
        return ParsedCommand(kind="ledger", name="history")
    if message == "/last-error":
        return ParsedCommand(kind="local", name="last-error")
    if message == "/tools":
        return ParsedCommand(kind="admin", name="tools", method="tools.list", params={})
    if message == "/context":
        return ParsedCommand(kind="admin", name="context", method="context.get", params={})
    if message == "/heatmap":
        return ParsedCommand(kind="admin", name="heatmap", method="heatmap.get", params={})

    return ParsedCommand(kind="unknown", name=message[1:])
