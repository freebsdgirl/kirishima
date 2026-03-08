from __future__ import annotations

import asyncio
import json
import time
import textwrap
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import RichLog, Static, TextArea

from cli.client import (
    AdminClient,
    AdminError,
    AdminRpcError,
    ChatClient,
    LedgerClient,
    LedgerMessage,
    _to_ledger_message,
)
from cli.commands import parse_command
from cli.transcript_renderer import TranscriptRenderer


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
        brain_base_url: str,
        ledger_base_url: str,
        user_id: str,
    ):
        super().__init__()
        self.chat_client = chat_client
        self.admin_client = AdminClient(brain_base_url)
        self.ledger_client = LedgerClient(ledger_base_url, user_id=user_id)
        self.current_model = default_model
        self.api_base_url = api_base_url
        self.brain_base_url = brain_base_url
        self.ledger_base_url = ledger_base_url
        self.user_id = user_id
        self._transcript: RichLog | None = None
        self._compose: TextArea | None = None
        self._status: Static | None = None
        self._send_task: asyncio.Task | None = None
        self._stream_task: asyncio.Task | None = None
        self._renderer: TranscriptRenderer | None = None
        self._last_error: AdminError | None = None

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
        self._renderer = TranscriptRenderer(self._write, self._content_width)
        self._write_system(
            f"API {self.api_base_url} | Brain {self.brain_base_url} | Ledger {self.ledger_base_url} | user={self.user_id} | mode={self.current_model} | Ctrl+S to send"
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
        command = parse_command(message)

        if command.kind == "local" and command.name == "help":
            self._render_help()
            return
        if command.kind == "local" and command.name == "clear":
            if self._transcript is not None:
                self._transcript.clear()
            if self._renderer is not None:
                self._renderer.reset_state()
            self._set_status("Cleared")
            return
        if command.kind == "local" and command.name == "exit":
            self.exit()
            return
        if command.kind == "local" and command.name == "last-error":
            self._show_last_error()
            return
        if command.kind == "local" and command.name == "mode" and message == "/mode":
            self._write_system(f"mode={self.current_model}")
            return
        if command.kind == "local" and command.name == "mode" and message.startswith("/mode "):
            next_mode = message[len("/mode ") :].strip()
            if not next_mode:
                self._write_error("Mode name is required.")
                return
            self.current_model = next_mode
            self._write_system(f"mode set to {self.current_model}")
            self._set_status(f"Mode={self.current_model}")
            return
        if command.kind == "ledger" and command.name == "history":
            await self._handle_history_command(message)
            return
        if command.kind == "admin" and command.method is not None:
            await self._handle_admin_command(command.name, command.method, command.params or {})
            return

        self._write_error(f"Unknown command: {message}. Try /help.")

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

    async def _handle_history_command(self, message: str) -> None:
        turns = 15
        if message.startswith("/history "):
            raw_turns = message[len("/history ") :].strip()
            if not raw_turns:
                self._write_error("Usage: /history <n>")
                return
            try:
                turns = int(raw_turns)
            except ValueError:
                self._write_error("Usage: /history <n>")
                return
            if turns <= 0:
                self._write_error("History turns must be >= 1.")
                return
        self._set_status(f"Loading history (turns={turns})...")
        try:
            messages = await self.ledger_client.get_history_turns(turns=turns)
        except Exception as exc:
            self._write_error(f"History load failed: {exc}")
            self._set_status("History load failed")
            return
        self._write_spacer()
        self._write_system(f"[history] last {turns} turns")
        for msg in messages:
            self._append_ledger_message(msg, dedupe=False)
        if self._transcript is not None:
            self._transcript.scroll_end(animate=False)
        self._set_status(f"History loaded ({turns} turns)")

    async def _handle_admin_command(self, command_name: str, method: str, params: dict[str, object]) -> None:
        self._set_status(f"Running {method}...")
        started = time.perf_counter()
        try:
            result = await self.admin_client.send_admin(method, params)
        except AdminRpcError as exc:
            self._cache_error(exc.code, exc.message, exc.data)
            self._write_admin_error(exc.code, exc.message, exc.data)
            self._set_status(f"{method} failed")
            return
        except Exception as exc:
            self._cache_error(-32000, str(exc), None)
            self._write_error(str(exc))
            self._set_status(f"{method} failed")
            return

        elapsed = time.perf_counter() - started
        self._last_error = None
        self._write_spacer()
        if command_name == "tools":
            self._render_tools_result(result)
        elif command_name == "context":
            self._render_context_result(result)
        elif command_name == "heatmap":
            self._render_heatmap_result(result)
        else:
            self._write_system(f"{method} completed")
        self._set_status(f"{elapsed:.2f}s | {method}")

    def _set_status(self, text: str) -> None:
        if self._status is not None:
            self._status.update(text)

    def _write_error(self, message: str) -> None:
        if self._renderer is not None:
            self._renderer.write_error(message)

    def _write_system(self, message: str) -> None:
        if self._renderer is not None:
            self._renderer.write_system(message)

    def _write(self, line: str) -> None:
        if self._transcript is not None:
            self._transcript.write(line, scroll_end=True)

    def _write_spacer(self) -> None:
        if self._renderer is not None:
            self._renderer.write_spacer()

    def _cache_error(self, code: int, message: str, data: dict[str, Any] | None) -> None:
        self._last_error = AdminError(code=code, message=message, data=data)

    def _show_last_error(self) -> None:
        if self._last_error is None:
            self._write_system("No cached error.")
            return
        self._write_admin_error(
            self._last_error.code,
            self._last_error.message,
            self._last_error.data,
        )

    def _write_admin_error(self, code: int, message: str, data: dict[str, Any] | None) -> None:
        service = ""
        status_code = ""
        if data:
            if data.get("service"):
                service = f" service={data['service']}"
            if data.get("status_code") is not None:
                status_code = f" status={data['status_code']}"
        self._write_error(f"[rpc {code}] {message}{service}{status_code}")

    def _render_help(self) -> None:
        self._write_system("[help] local")
        self._write("  /help                show commands")
        self._write("  /mode                show current CLI session mode")
        self._write("  /mode <name>         set current CLI session mode")
        self._write("  /clear               clear transcript")
        self._write("  /last-error          show last admin error")
        self._write("  /exit                quit")
        self._write_spacer()
        self._write_system("[help] ledger")
        self._write("  /history [n]         show recent turn history from ledger")
        self._write_spacer()
        self._write_system("[help] admin")
        self._write("  /tools               list registered brain tools")
        self._write("  /context             show contextual memories + top keywords")
        self._write("  /heatmap             show full keyword heatmap state")
        self._write_spacer()
        self._write_system("[help] send")
        self._write("  Ctrl+S to send the current draft")

    def _render_tools_result(self, result: dict[str, Any]) -> None:
        self._write_system("[tools]")
        tools = result.get("tools")
        if not isinstance(tools, list) or not tools:
            self._write("No tools registered.")
            return
        self._write(f"{len(tools)} tool(s)")
        self._write_spacer()
        for tool in tools:
            if not isinstance(tool, dict):
                continue
            name = str(tool.get("name") or "unknown")
            description = str(tool.get("description") or "").strip()
            flags: list[str] = []
            if tool.get("always"):
                flags.append("always")
            if tool.get("persistent"):
                flags.append("persistent")
            clients = tool.get("clients")
            if isinstance(clients, list) and clients:
                flags.append("clients=" + ",".join(str(item) for item in clients))
            flag_text = f" [{' | '.join(flags)}]" if flags else ""
            self._write(f"[bold bright_cyan]{name}[/bold bright_cyan]{flag_text}")
            if description:
                for line in self._wrap_text(description, indent="  "):
                    self._write(line)

    def _render_context_result(self, result: dict[str, Any]) -> None:
        self._write_system("[context] contextual memories")
        memories = result.get("memories")
        if isinstance(memories, list) and memories:
            for index, memory in enumerate(memories, start=1):
                wrapped = self._wrap_text(str(memory), indent=f"{index:>2}. ", subsequent="    ")
                for line in wrapped:
                    self._write(line)
        else:
            self._write("No contextual memories found.")

        self._write_spacer()
        self._write_system("[context] keyword summary")
        self._render_score_lines(result.get("scores"), limit=10)

    def _render_heatmap_result(self, result: dict[str, Any]) -> None:
        self._write_system("[heatmap] keyword state")
        self._render_score_lines(result.get("scores"), limit=None)

    def _render_score_lines(self, scores_payload: object, limit: int | None) -> None:
        if not isinstance(scores_payload, dict) or not scores_payload:
            self._write("No keyword scores found.")
            return
        entries: list[tuple[str, float]] = []
        for keyword, score in scores_payload.items():
            try:
                entries.append((str(keyword), float(score)))
            except (TypeError, ValueError):
                continue
        entries.sort(key=lambda item: item[1], reverse=True)
        total_entries = len(entries)
        if limit is not None:
            entries = entries[:limit]
        shown_suffix = f" showing {len(entries)}" if limit is not None else ""
        self._write(f"{total_entries} keyword(s){shown_suffix}")
        self._write_spacer()
        for keyword, score in entries:
            self._write(f"{keyword:<24} {score:.3f}")

    def _wrap_text(
        self,
        text: str,
        indent: str = "",
        subsequent: str | None = None,
    ) -> list[str]:
        width = max(20, self._content_width() - 2)
        wrapped = textwrap.wrap(
            text,
            width=width,
            initial_indent=indent,
            subsequent_indent=subsequent if subsequent is not None else indent,
            replace_whitespace=False,
            drop_whitespace=True,
            break_long_words=True,
            break_on_hyphens=False,
        )
        if not wrapped:
            return [indent.rstrip()]
        return wrapped

    def _content_width(self) -> int:
        if self._transcript is not None and self._transcript.size.width > 0:
            return max(20, self._transcript.size.width - 2)
        return 120

    def _append_ledger_message(self, msg: LedgerMessage, dedupe: bool = True) -> None:
        if self._renderer is not None:
            self._renderer.append_ledger_message(msg, dedupe=dedupe)


def _or_dash(value: int | None) -> str:
    return "-" if value is None else str(value)
