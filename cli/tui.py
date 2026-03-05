from __future__ import annotations

import asyncio
import time

from rich.markup import escape as escape_markup
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.widgets import RichLog, Static, TextArea

from cli.client import ChatClient


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

    def __init__(self, chat_client: ChatClient, default_model: str, api_base_url: str):
        super().__init__()
        self.chat_client = chat_client
        self.current_model = default_model
        self.api_base_url = api_base_url
        self._transcript: RichLog | None = None
        self._compose: TextArea | None = None
        self._status: Static | None = None
        self._send_task: asyncio.Task | None = None
        self._has_chat_turns = False

    def compose(self) -> ComposeResult:
        with Vertical(id="layout"):
            yield RichLog(id="transcript", markup=True, wrap=True, highlight=False)
            yield TextArea(id="compose")
            yield Static(id="status")

    def on_mount(self) -> None:
        self._transcript = self.query_one("#transcript", RichLog)
        self._compose = self.query_one("#compose", TextArea)
        self._status = self.query_one("#status", Static)

        self._compose.focus()
        self._compose.border_title = "[bold blue]Message (Enter=newline, Ctrl+S=send)[/]"
        self._transcript.border_title = "[bold blue]Kirishima[/]"
        self._write_system(
            f"Connected to {self.api_base_url} | mode={self.current_model} | Ctrl+S to send"
        )
        self._set_status("Ready")

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

            self._write_user(message)
            self._set_status("Sending...")
            started = time.perf_counter()

            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, self.chat_client.send_chat, message, self.current_model
            )
            elapsed = time.perf_counter() - started
            self._write_spacer()
            self._write_assistant(result.text or "[empty response]")
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

    async def _handle_command(self, message: str) -> None:
        if message == "/help":
            self._write_system(
                "Commands: /help, /mode, /mode <name>, /clear, /exit | Send: Ctrl+S"
            )
            return
        if message == "/clear":
            if self._transcript is not None:
                self._transcript.clear()
            self._has_chat_turns = False
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

    def _set_status(self, text: str) -> None:
        if self._status is not None:
            self._status.update(text)

    def _write_user(self, message: str) -> None:
        if self._has_chat_turns:
            self._write_spacer()
        self._write(
            f"[bold bright_magenta]\\[user][/bold bright_magenta] {escape_markup(message)}"
        )
        self._has_chat_turns = True

    def _write_assistant(self, message: str) -> None:
        self._write(
            f"[bold bright_cyan]\\[kirishima][/bold bright_cyan] {escape_markup(message)}"
        )
        self._has_chat_turns = True

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


def _or_dash(value: int | None) -> str:
    return "-" if value is None else str(value)
