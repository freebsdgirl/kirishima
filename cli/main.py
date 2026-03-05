from __future__ import annotations

import argparse

from cli.client import ChatClient
from cli.config import CliConfig
from cli.tui import KirishimaChatApp


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
        print(f"error> {exc}")
        return 1

    app = KirishimaChatApp(
        chat_client=chat_client,
        default_model=config.default_model,
        api_base_url=config.api_base_url,
    )
    app.run(mouse=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
