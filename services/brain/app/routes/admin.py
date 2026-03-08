from __future__ import annotations

import json
import os
from typing import Any, Awaitable, Callable

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.tools import get_all_registered_names, get_tool_meta
from app.util import TIMEOUT
from shared.log_config import get_logger


logger = get_logger(f"brain.{__name__}")
router = APIRouter()

JsonRpcHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

DEFAULT_CONTEXT_LIMIT = 5


def _success(request_id: Any, result: dict[str, Any]) -> JSONResponse:
    return JSONResponse({"jsonrpc": "2.0", "id": request_id, "result": result})


def _error(
    request_id: Any,
    code: int,
    message: str,
    data: dict[str, Any] | None = None,
) -> JSONResponse:
    payload: dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
    if data:
        payload["error"]["data"] = data
    return JSONResponse(payload)


async def _ledger_get(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    ledger_port = os.getenv("LEDGER_PORT", "4203")
    url = f"http://ledger:{ledger_port}{path}"
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        logger.error("Ledger request failed: %s %s", path, exc)
        raise AdminRouteError(
            code=-32002,
            message="Ledger request failed.",
            data={"service": "ledger", "status_code": exc.response.status_code},
        ) from exc
    except httpx.HTTPError as exc:
        logger.error("Ledger request error: %s %s", path, exc)
        raise AdminRouteError(
            code=-32002,
            message="Ledger request failed.",
            data={"service": "ledger"},
        ) from exc
    except ValueError as exc:
        logger.error("Ledger returned invalid JSON: %s", path)
        raise AdminRouteError(
            code=-32003,
            message="Ledger returned invalid JSON.",
            data={"service": "ledger"},
        ) from exc

    if not isinstance(payload, dict):
        raise AdminRouteError(
            code=-32003,
            message="Ledger returned an unexpected payload.",
            data={"service": "ledger"},
        )
    return payload


class AdminRouteError(Exception):
    def __init__(self, code: int, message: str, data: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


async def _tools_list(_params: dict[str, Any]) -> dict[str, Any]:
    tools: list[dict[str, Any]] = []
    for name in sorted(get_all_registered_names()):
        meta = get_tool_meta(name)
        if meta is None:
            continue
        tools.append(
            {
                "name": meta.name,
                "description": meta.description,
                "always": meta.always,
                "persistent": meta.persistent,
                "clients": meta.clients,
            }
        )
    return {"tools": tools}


async def _context_get(params: dict[str, Any]) -> dict[str, Any]:
    limit = params.get("limit", DEFAULT_CONTEXT_LIMIT)
    if not isinstance(limit, int) or limit <= 0:
        raise AdminRouteError(code=-32602, message="Invalid params: limit must be a positive integer.")

    context_payload, scores_payload = await _fetch_context_and_scores(limit)
    return {
        "memories": context_payload.get("memories", []),
        "scores": scores_payload.get("scores", {}),
    }


async def _fetch_context_and_scores(limit: int) -> tuple[dict[str, Any], dict[str, Any]]:
    context_payload = await _ledger_get("/context/", params={"limit": limit})
    scores_payload = await _ledger_get("/context/keyword_scores")
    return context_payload, scores_payload


async def _heatmap_get(_params: dict[str, Any]) -> dict[str, Any]:
    scores_payload = await _ledger_get("/context/keyword_scores")
    return {"scores": scores_payload.get("scores", {})}


METHODS: dict[str, JsonRpcHandler] = {
    "tools.list": _tools_list,
    "context.get": _context_get,
    "heatmap.get": _heatmap_get,
}


@router.post("/admin/rpc")
async def admin_rpc(request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return _error(None, -32700, "Parse error")

    if not isinstance(payload, dict):
        return _error(None, -32600, "Invalid Request")

    request_id = payload.get("id")
    if payload.get("jsonrpc") != "2.0" or "method" not in payload:
        return _error(request_id, -32600, "Invalid Request")

    method = payload.get("method")
    params = payload.get("params", {})

    if not isinstance(method, str):
        return _error(request_id, -32600, "Invalid Request")
    if not isinstance(params, dict):
        return _error(request_id, -32602, "Invalid params")

    handler = METHODS.get(method)
    if handler is None:
        return _error(request_id, -32601, f"Method '{method}' not found")

    try:
        result = await handler(params)
    except AdminRouteError as exc:
        return _error(request_id, exc.code, exc.message, exc.data)
    except Exception as exc:
        logger.exception("Unhandled admin RPC error for method %s: %s", method, exc)
        return _error(request_id, -32603, "Internal error")

    return _success(request_id, result)
