from __future__ import annotations

import importlib.util
import asyncio
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
ADMIN_ROUTE_PATH = ROOT / "services" / "brain" / "app" / "routes" / "admin.py"


def _load_admin_module():
    logger = types.SimpleNamespace(error=lambda *a, **k: None, exception=lambda *a, **k: None)

    app_pkg = types.ModuleType("app")
    tools_module = types.ModuleType("app.tools")
    util_module = types.ModuleType("app.util")
    shared_pkg = types.ModuleType("shared")
    log_config_module = types.ModuleType("shared.log_config")

    tools_module.get_all_registered_names = lambda: ["memory", "manage_prompt"]
    tools_module.get_tool_meta = lambda name: types.SimpleNamespace(
        name=name,
        description=f"{name} description",
        always=name == "memory",
        persistent=True,
        clients=["internal"],
    )
    util_module.TIMEOUT = 5
    log_config_module.get_logger = lambda _name: logger

    original_modules = {
        key: sys.modules.get(key)
        for key in ("app", "app.tools", "app.util", "shared", "shared.log_config")
    }
    sys.modules.update(
        {
            "app": app_pkg,
            "app.tools": tools_module,
            "app.util": util_module,
            "shared": shared_pkg,
            "shared.log_config": log_config_module,
        }
    )

    try:
        spec = importlib.util.spec_from_file_location("brain_admin_route_test_module", ADMIN_ROUTE_PATH)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        return module
    finally:
        for name, original in original_modules.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


class AdminRpcRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.admin = _load_admin_module()

    def setUp(self):
        self._methods = dict(self.admin.METHODS)

    def tearDown(self):
        self.admin.METHODS = dict(self._methods)

    def test_tools_list_returns_registered_tools(self):
        response = self._rpc(
            {"jsonrpc": "2.0", "id": "tools-1", "method": "tools.list", "params": {}}
        )

        payload = response.body_json
        self.assertEqual(payload["id"], "tools-1")
        self.assertEqual(payload["jsonrpc"], "2.0")
        self.assertEqual(
            payload["result"]["tools"],
            [
                {
                    "name": "manage_prompt",
                    "description": "manage_prompt description",
                    "always": False,
                    "persistent": True,
                    "clients": ["internal"],
                },
                {
                    "name": "memory",
                    "description": "memory description",
                    "always": True,
                    "persistent": True,
                    "clients": ["internal"],
                },
            ],
        )

    def test_context_get_validates_limit(self):
        response = self._rpc(
            {"jsonrpc": "2.0", "id": "context-bad", "method": "context.get", "params": {"limit": 0}}
        )

        payload = response.body_json
        self.assertEqual(payload["error"]["code"], -32602)
        self.assertIn("positive integer", payload["error"]["message"])

    def test_context_get_returns_memories_and_scores(self):
        with patch.object(
            self.admin,
            "_fetch_context_and_scores",
            AsyncMock(return_value=({"memories": [{"id": 1, "text": "hi"}]}, {"scores": {"python": 3}})),
        ) as fetch_mock:
            response = self._rpc(
                {"jsonrpc": "2.0", "id": "context-ok", "method": "context.get", "params": {"limit": 2}}
            )

        payload = response.body_json
        self.assertEqual(payload["result"], {"memories": [{"id": 1, "text": "hi"}], "scores": {"python": 3}})
        fetch_mock.assert_awaited_once_with(2)

    def test_invalid_request_shape_returns_json_rpc_error(self):
        response = self._rpc(["definitely", "not", "an", "object"])

        payload = response.body_json
        self.assertEqual(payload["error"]["code"], -32600)
        self.assertEqual(payload["error"]["message"], "Invalid Request")

    def test_invalid_json_returns_parse_error(self):
        response = self._rpc(json.JSONDecodeError("bad json", "{bad json", 1))

        payload = response.body_json
        self.assertEqual(payload["error"]["code"], -32700)
        self.assertEqual(payload["error"]["message"], "Parse error")

    def test_unknown_method_returns_method_not_found(self):
        response = self._rpc(
            {"jsonrpc": "2.0", "id": "nope", "method": "nope.method", "params": {}}
        )

        payload = response.body_json
        self.assertEqual(payload["error"]["code"], -32601)
        self.assertIn("not found", payload["error"]["message"])

    def test_internal_exception_maps_to_internal_error(self):
        with patch.object(
            self.admin,
            "_tools_list",
            AsyncMock(side_effect=RuntimeError("boom")),
        ):
            self.admin.METHODS["tools.list"] = self.admin._tools_list
            response = self._rpc(
                {"jsonrpc": "2.0", "id": "explode", "method": "tools.list", "params": {}}
            )

        payload = response.body_json
        self.assertEqual(payload["error"]["code"], -32603)
        self.assertEqual(payload["error"]["message"], "Internal error")

    def _rpc(self, payload):
        request = DummyRequest(payload)
        response = asyncio.run(self.admin.admin_rpc(request))
        response.body_json = json.loads(response.body.decode("utf-8"))
        return response


class AdminClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_send_admin_raises_structured_error(self):
        from cli.client import AdminClient, AdminRpcError

        request = httpx_request(
            "POST",
            "http://brain.test/admin/rpc",
        )
        response = httpx_response(
            200,
            request,
            {
                "jsonrpc": "2.0",
                "id": "fixed-id",
                "error": {"code": -32002, "message": "Ledger request failed.", "data": {"service": "ledger"}},
            },
        )

        with patch("cli.client.uuid4", return_value="fixed-id"), patch("httpx.AsyncClient.post", AsyncMock(return_value=response)):
            with self.assertRaises(AdminRpcError) as ctx:
                await AdminClient("http://brain.test").send_admin("context.get", {"limit": 3})

        self.assertEqual(ctx.exception.code, -32002)
        self.assertEqual(ctx.exception.message, "Ledger request failed.")
        self.assertEqual(ctx.exception.data, {"service": "ledger"})

    async def test_send_admin_rejects_mismatched_response_id(self):
        from cli.client import AdminClient

        request = httpx_request(
            "POST",
            "http://brain.test/admin/rpc",
        )
        response = httpx_response(
            200,
            request,
            {"jsonrpc": "2.0", "id": "wrong-id", "result": {"tools": []}},
        )

        with patch("cli.client.uuid4", return_value="expected-id"), patch("httpx.AsyncClient.post", AsyncMock(return_value=response)):
            with self.assertRaises(RuntimeError) as ctx:
                await AdminClient("http://brain.test").send_admin("tools.list")

        self.assertIn("did not match", str(ctx.exception))


def httpx_request(method: str, url: str):
    import httpx

    return httpx.Request(method, url)


def httpx_response(status_code: int, request, payload: dict[str, object]):
    import httpx

    return httpx.Response(status_code=status_code, request=request, content=json.dumps(payload).encode("utf-8"))


class DummyRequest:
    def __init__(self, payload):
        self._payload = payload

    async def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload
