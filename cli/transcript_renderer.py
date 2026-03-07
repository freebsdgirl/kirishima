from __future__ import annotations

import textwrap
from typing import Callable

from rich.markup import escape as escape_markup
from rich.text import Text

from cli.client import LedgerMessage


class TranscriptRenderer:
    def __init__(self, write_fn: Callable[[str | Text], None], width_fn: Callable[[], int]):
        self._write_fn = write_fn
        self._width_fn = width_fn
        self._seen_message_ids: set[int] = set()
        self._has_rows = False
        self._last_rendered_kind: str | None = None

    def reset_state(self) -> None:
        self._seen_message_ids.clear()
        self._has_rows = False
        self._last_rendered_kind = None

    def write_spacer(self) -> None:
        self._write_fn("")

    def write_system(self, message: str) -> None:
        self._write_fn(
            f"[bold dodger_blue2]\\[system][/bold dodger_blue2] "
            f"[dim]{escape_markup(message)}[/]"
        )

    def write_error(self, message: str) -> None:
        self._write_fn(f"[bold red]\\[error][/bold red] {escape_markup(message)}")

    def append_ledger_message(self, msg: LedgerMessage, dedupe: bool = True) -> None:
        if dedupe and msg.id and msg.id in self._seen_message_ids:
            return
        if msg.id:
            self._seen_message_ids.add(msg.id)

        if msg.role == "user":
            self._write_user(msg.content)
            return
        if msg.role == "assistant":
            if msg.tool_calls:
                if self._last_rendered_kind in {"user", "tool", "tool_call"}:
                    self.write_spacer()
                self._write_tool_call(msg.tool_calls)
            elif msg.content:
                self._write_assistant(msg.content)
            return
        if msg.role == "tool":
            self._write_tool_output(msg.content)
            return
        self.write_system(f"{msg.role}: {msg.content}")

    def _write_user(self, message: str) -> None:
        if self._has_rows:
            self.write_spacer()
        bg = "on #4a4a4a"
        label = "[user]"
        first_prefix = f"{label} "
        width = self._width_fn()

        paragraphs = message.splitlines() or [""]
        visual_lines: list[str] = []
        for p_idx, paragraph in enumerate(paragraphs):
            if p_idx == 0:
                wrapped = textwrap.wrap(
                    paragraph,
                    width=width,
                    initial_indent=first_prefix,
                    subsequent_indent="",
                    replace_whitespace=False,
                    drop_whitespace=True,
                    break_long_words=True,
                    break_on_hyphens=False,
                )
                if not wrapped:
                    wrapped = [first_prefix]
            else:
                wrapped = textwrap.wrap(
                    paragraph,
                    width=width,
                    replace_whitespace=False,
                    drop_whitespace=True,
                    break_long_words=True,
                    break_on_hyphens=False,
                )
                if not wrapped:
                    wrapped = [""]
            visual_lines.extend(wrapped)

        for idx, chunk in enumerate(visual_lines):
            line = Text(chunk, style=bg)
            if idx == 0 and chunk.startswith(first_prefix):
                line.stylize(f"bold bright_magenta {bg}", 0, len(label))
            pad = width - line.cell_len
            if pad > 0:
                line.append(" " * pad, style=bg)
            self._write_fn(line)
        self._has_rows = True
        self._last_rendered_kind = "user"

    def _write_assistant(self, message: str) -> None:
        if self._has_rows:
            self.write_spacer()
        self._write_fn(
            f"[bold bright_cyan]\\[kirishima][/bold bright_cyan] {escape_markup(message)}"
        )
        self._has_rows = True
        self._last_rendered_kind = "assistant"

    def _write_tool_call(self, tool_calls: dict[str, object]) -> None:
        fn_name = "unknown"
        args = ""
        if tool_calls.get("function") and isinstance(tool_calls["function"], dict):
            fn_name = str(tool_calls["function"].get("name") or fn_name)
            args = str(tool_calls["function"].get("arguments") or "")
        self._write_fn(
            f"[bold orange3]\\[tool][/bold orange3] "
            f"{escape_markup(fn_name)}"
            + (f" {escape_markup(args)}" if args else "")
        )
        self._has_rows = True
        self._last_rendered_kind = "tool_call"

    def _write_tool_output(self, message: str) -> None:
        self._write_fn(escape_markup(message))
        self._has_rows = True
        self._last_rendered_kind = "tool"
