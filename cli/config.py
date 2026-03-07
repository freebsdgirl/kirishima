from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import os
from typing import Any


DEFAULT_API_PORT = "4200"
DEFAULT_LEDGER_PORT = "4203"
DEFAULT_MODEL = "default"


def _clean_env_value(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().strip('"').strip("'")


@dataclass(frozen=True)
class CliConfig:
    api_base_url: str
    ledger_base_url: str
    user_id: str
    default_model: str
    env_file: str

    @classmethod
    def from_sources(cls, args: Any) -> "CliConfig":
        env_file = str(getattr(args, "env_file", ".env"))
        dotenv_values = _load_dotenv(env_file)
        kirishima_config_values = _load_kirishima_config()

        api_url_arg = getattr(args, "api_url", None)
        api_port_arg = getattr(args, "api_port", None)
        ledger_url_arg = getattr(args, "ledger_url", None)
        ledger_port_arg = getattr(args, "ledger_port", None)
        if api_url_arg:
            api_base_url = api_url_arg.rstrip("/")
        else:
            api_port = (
                str(api_port_arg)
                if api_port_arg
                else _clean_env_value(os.getenv("API_PORT"))
                or dotenv_values.get("API_PORT")
                or DEFAULT_API_PORT
            )
            api_base_url = f"http://localhost:{api_port}/v1"

        if ledger_url_arg:
            ledger_base_url = ledger_url_arg.rstrip("/")
        else:
            ledger_port = (
                str(ledger_port_arg)
                if ledger_port_arg
                else _clean_env_value(os.getenv("LEDGER_PORT"))
                or dotenv_values.get("LEDGER_PORT")
                or DEFAULT_LEDGER_PORT
            )
            ledger_base_url = f"http://localhost:{ledger_port}"

        default_model = (
            _clean_env_value(getattr(args, "model", None))
            or _clean_env_value(os.getenv("LLM_MODEL_NAME"))
            or dotenv_values.get("LLM_MODEL_NAME")
            or DEFAULT_MODEL
        )
        user_id = _clean_env_value(str(kirishima_config_values.get("user_id", ""))) or ""
        if not user_id:
            raise RuntimeError(
                "Missing user_id in ~/.kirishima/config.json (or KIRISHIMA_CONFIG target file)."
            )

        return cls(
            api_base_url=api_base_url,
            ledger_base_url=ledger_base_url,
            user_id=user_id,
            default_model=default_model,
            env_file=env_file,
        )


def _load_dotenv(env_file: str) -> dict[str, str]:
    env_path = Path(env_file)
    if not env_path.exists():
        return {}

    try:
        from dotenv import dotenv_values
    except ImportError:
        return _parse_dotenv_fallback(env_path)

    parsed = dotenv_values(env_path)
    cleaned: dict[str, str] = {}
    for key, value in parsed.items():
        if value is None:
            continue
        cleaned[key] = _clean_env_value(value) or ""
    return cleaned


def _parse_dotenv_fallback(env_path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, raw_value = stripped.split("=", 1)
        values[key.strip()] = _clean_env_value(raw_value) or ""
    return values


def _load_kirishima_config() -> dict[str, Any]:
    config_path = Path(
        _clean_env_value(os.getenv("KIRISHIMA_CONFIG")) or str(Path.home() / ".kirishima" / "config.json")
    )
    if not config_path.exists():
        return {}
    try:
        raw = json.loads(config_path.read_text())
    except Exception:
        return {}
    return raw if isinstance(raw, dict) else {}
