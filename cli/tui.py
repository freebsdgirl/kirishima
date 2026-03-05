from __future__ import annotations

import asyncio
import json
import textwrap
import time

from rich.markup import escape as escape_markup
from rich.text import Text
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import RichLog, Static, TextArea

from cli.client import ChatClient, LedgerClient, LedgerMessage, _to_ledger_message


class KirishimaChatApp(App[None]):
    BINDINGS = [
        Binding("ctrl+s", "send_message", "Send"),
        Binding("ctrl+c", "quit", "Quit"),
    ]

    CSS = """
    #layout {
        height: 100%;
    }
    #transcript {
        height: 1fr;
        border: round blue;
    }
    #compose {
        height: 8;
        border: round blue;
    }
    #status {
        height: 1;
        color: $text-muted;
    }
    """

    def __init__(
        self,
        chat_client: ChatClient,
        default_model: str,
        api_base_url: str,
        ledger_base_url: str,
    ):
        super().__init__()
        self.chat_client = chat_client
        self.ledger_client = LedgerClient(ledger_base_url)
        self.current_model = default_model
        self.api_base_url = api_base_url
        self.ledger_base_url = ledger_base_url
        self._transcript: RichLog | None = None
        self._compose: TextArea | None = None
        self._status: Static | None = None
        self._send_task: asyncio.Task | None = None
        self._stream_task: asyncio.Task | None = None
        self._seen_message_ids: set[int] = set()
        self._has_rows = False
        self._last_rendered_kind: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="layout"):
            yield RichLog(id="transcript", markup=True, wrap=True, highlight=False)
            yield TextArea(id="compose")
            yield Static(id="status")

    async def on_mount(self) -> None:
        self._transcript = self.query_one("#transcript", RichLog)
        self._compose = self.query_one("#compose", TextArea)
        self._status = self.query_one("#status", Static)

        self._compose.focus()
        self._compose.border_title = "[bold blue]Message (Enter=newline, Ctrl+S=send)[/]"
        self._transcript.border_title = "[bold blue]Kirishima[/]"
        self._write_system(
            f"API {self.api_base_url} | Ledger {self.ledger_base_url} | mode={self.current_model} | Ctrl+S to send"
        )
        self._set_status("Loading recent history...")
        await self._load_recent_history()
        self._set_status("Ready")
        self._stream_task = asyncio.create_task(self._consume_ledger_stream())

    async def action_send_message(self) -> None:
        if self._compose is None:
            return

        raw = self._compose.text
        message = raw.strip()
        if not message:
            return

        if self._send_task and not self._send_task.done() and not message.startswith("/"):
            self._write_error("A request is already in progress. Keep typing, then press Ctrl+S after it finishes.")
            self._compose.text = message
            return

        self._set_status("Queued...")
        try:
            self._send_task = asyncio.create_task(self._handle_input(message))
        except Exception as exc:
            self._write_error(f"Failed to queue request: {exc}")
            self._set_status("Queue failed")
            return

        self._compose.text = ""
        self._compose.focus()

    async def _handle_input(self, message: str) -> None:
        is_chat_message = not message.startswith("/")
        try:
            if not is_chat_message:
                await self._handle_command(message)
                return

            self._set_status("Sending...")
            started = time.perf_counter()

            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, self.chat_client.send_chat, message, self.current_model
            )
            elapsed = time.perf_counter() - started
            self._set_status(
                f"{elapsed:.2f}s | model={self.current_model} | "
                f"prompt={_or_dash(result.usage.prompt_tokens)} "
                f"completion={_or_dash(result.usage.completion_tokens)} "
                f"total={_or_dash(result.usage.total_tokens)}"
            )
        except Exception as exc:
            self._write_error(str(exc))
            self._set_status("Request failed")
            if is_chat_message and self._compose is not None and not self._compose.text.strip():
                # Don't lose the user's draft on failed sends.
                self._compose.text = message
                self._compose.focus()

    async def on_unmount(self) -> None:
        if self._stream_task and not self._stream_task.done():
            self._stream_task.cancel()

    async def _handle_command(self, message: str) -> None:
        if message == "/help":
            self._write_system(
                "Commands: /help, /mode, /mode <name>, /clear, /exit | Send: Ctrl+S"
            )
            return
        if message == "/clear":
            if self._transcript is not None:
                self._transcript.clear()
            self._has_rows = False
            self._last_rendered_kind = None
            self._set_status("Cleared")
            return
        if message == "/exit":
            self.exit()
            return
        if message == "/mode":
            self._write_system(f"mode={self.current_model}")
            return
        if message.startswith("/mode "):
            next_mode = message[len("/mode ") :].strip()
            if not next_mode:
                self._write_error("Mode name is required.")
                return
            self.current_model = next_mode
            self._write_system(f"mode set to {self.current_model}")
            self._set_status(f"Mode={self.current_model}")
            return

        self._write_system("Admin commands not implemented yet.")

    async def _load_recent_history(self) -> None:
        try:
            messages = await self.ledger_client.get_recent_messages()
        except Exception as exc:
            self._write_error(f"History preload failed: {exc}")
            return
        for msg in messages:
            self._append_ledger_message(msg)

    async def _consume_ledger_stream(self) -> None:
        while True:
            try:
                async for event_name, data in self.ledger_client.stream_messages():
                    if event_name != "message":
                        continue
                    try:
                        payload = json.loads(data)
                    except Exception:
                        self._write_error(f"Invalid stream payload: {data[:160]}")
                        continue
                    msg = _to_ledger_message(payload)
                    self._append_ledger_message(msg)
            except Exception as exc:
                self._write_error(f"Ledger stream disconnected: {exc}")
                self._set_status("Ledger stream disconnected; retrying...")
                await asyncio.sleep(1.0)

    def _set_status(self, text: str) -> None:
        if self._status is not None:
            self._status.update(text)

    def _write_user(self, message: str) -> None:
        if self._has_rows:
            self._write_spacer()
        bg = "on #4a4a4a"
        label = "[user]"
        first_prefix = f"{label} "
        width = 120
        if self._transcript is not None and self._transcript.size.width > 0:
            width = self._transcript.size.width
        first_width = max(1, width - len(first_prefix))
        next_width = max(1, width)

        paragraphs = message.splitlines() or [""]
        logical_lines: list[str] = []
        for p_idx, paragraph in enumerate(paragraphs):
            first_chunks = textwrap.wrap(
                paragraph,
                width=first_width if p_idx == 0 else next_width,
                replace_whitespace=False,
                drop_whitespace=False,
                break_long_words=True,
                break_on_hyphens=False,
            )
            if not first_chunks:
                first_chunks = [""]
            if p_idx == 0:
                logical_lines.append(first_chunks[0])
                if len(first_chunks) > 1:
                    logical_lines.extend(first_chunks[1:])
            else:
                logical_lines.extend(first_chunks)

        for idx, chunk in enumerate(logical_lines):
            if idx == 0:
                line = Text(first_prefix + chunk, style=bg)
                line.stylize(f"bold bright_magenta {bg}", 0, len(label))
            else:
                line = Text(chunk, style=bg)
            pad = width - line.cell_len
            if pad > 0:
                line.append(" " * pad, style=bg)
            self._write(line)
        self._has_rows = True
        self._last_rendered_kind = "user"

    def _write_assistant(self, message: str) -> None:
        if self._has_rows:
            self._write_spacer()
        self._write(
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
        self._write(
            f"[bold orange3]\\[tool][/bold orange3] "
            f"{escape_markup(fn_name)}"
            + (f" {escape_markup(args)}" if args else "")
        )
        self._has_rows = True
        self._last_rendered_kind = "tool_call"

    def _write_tool_output(self, message: str, tool_call_id: str | None) -> None:
        self._write(escape_markup(message))
        self._has_rows = True
        self._last_rendered_kind = "tool"

    # Future tool rendering note:
    # Add a `_write_tool` formatter with an orange label, e.g. `[bold orange3][tool][/bold orange3]`,
    # once tool-call rows are added to the transcript.

    def _write_error(self, message: str) -> None:
        self._write(f"[bold red]\\[error][/bold red] {escape_markup(message)}")

    def _write_system(self, message: str) -> None:
        self._write(
            f"[bold dodger_blue2]\\[system][/bold dodger_blue2] "
            f"[dim]{escape_markup(message)}[/]"
        )

    def _write(self, line: str) -> None:
        if self._transcript is not None:
            self._transcript.write(line, scroll_end=True)

    def _write_spacer(self) -> None:
        self._write("")

    def _append_ledger_message(self, msg: LedgerMessage) -> None:
        if msg.id and msg.id in self._seen_message_ids:
            return
        if msg.id:
            self._seen_message_ids.add(msg.id)

        if msg.role == "user":
            self._write_user(msg.content)
            return
        if msg.role == "assistant":
            if msg.tool_calls:
                if self._last_rendered_kind in {"user", "tool", "tool_call"}:
                    self._write_spacer()
                self._write_tool_call(msg.tool_calls)
            elif msg.content:
                self._write_assistant(msg.content)
            return
        if msg.role == "tool":
            self._write_tool_output(msg.content, msg.tool_call_id)
            return
        self._write_system(f"{msg.role}: {msg.content}")


def _or_dash(value: int | None) -> str:
    return "-" if value is None else str(value)
