from __future__ import annotations

import argparse
import sys
import time

from cli.client import ChatClient
from cli.config import CliConfig
from cli.render import render_assistant_reply, render_error, render_help


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Kirishima CLI (chat path only)")
    parser.add_argument("--env-file", default=".env", help="Path to .env file")
    parser.add_argument("--api-port", type=int, help="API service port (localhost)")
    parser.add_argument("--api-url", help="Full API base URL (e.g. http://localhost:4200/v1)")
    parser.add_argument("--model", help="Default mode/model for the chat session")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = CliConfig.from_sources(args)

    try:
        chat_client = ChatClient(config.api_base_url)
    except Exception as exc:
        render_error(str(exc))
        return 1

    current_model = config.default_model
    print(f"Kirishima CLI chat mode. API: {config.api_base_url} | model: {current_model}")
    print("Type /help for local commands.")

    while True:
        try:
            raw = input("you> ")
        except KeyboardInterrupt:
            print()
            continue
        except EOFError:
            print("\nExiting.")
            break

        message = raw.strip()
        if not message:
            continue

        if message.startswith("/"):
            if message == "/help":
                render_help()
                continue
            if message == "/clear":
                print("\033[2J\033[H", end="")
                continue
            if message == "/exit":
                break
            if message == "/mode":
                print(f"mode> {current_model}")
                continue
            if message.startswith("/mode "):
                next_mode = message[len("/mode ") :].strip()
                if not next_mode:
                    render_error("Mode name is required.")
                else:
                    current_model = next_mode
                    print(f"mode> set to {current_model}")
                continue

            print("Admin commands not implemented yet.")
            continue

        started = time.perf_counter()
        try:
            result = chat_client.send_chat(message=message, model=current_model)
        except Exception as exc:
            render_error(str(exc))
            continue

        elapsed = time.perf_counter() - started
        render_assistant_reply(
            text=result.text,
            duration_s=elapsed,
            usage=result.usage,
            model=current_model,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
