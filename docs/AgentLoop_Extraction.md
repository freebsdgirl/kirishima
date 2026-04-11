# AgentLoop Extraction

## 1. Motivation

`services/brain/app/message/multiturn.py` currently contains a 383-line orchestration function. Roughly 90 of those lines (`multiturn.py:261-357`) are a tool-call loop: send to proxy, inspect `ProxyResponse.tool_calls`, dispatch each call via `call_tool`, sync the call and result to ledger, append the messages back into the conversation, repeat until the model returns content or `max_iterations = 10` is hit.

The sub-agent design in `docs/Subagent_Design.md` proposes a new worker runtime under `services/brain/app/subagents/runtime.py` that "reuses the same general proxy/tool-call mechanics as top-level chat" (§18). Read literally, that is two tool loops: the existing one in `multiturn.py`, and a second one in `runtime.py`. Any future change — streaming, cancellation, richer trace logging, different budgets, new response shapes from the OpenAI Responses API migration — would have to land in both places.

This document describes extracting the tool loop into a single `AgentLoop` primitive that both `multiturn.py` (top-level supervisor) and `subagents/runtime.py` (worker) can configure and invoke. The extraction is a prerequisite to sub-agent phase 1: when phase 1 lands, it writes a small caller around `AgentLoop`, not a second loop.

The extraction is also orthogonal to the in-flight OpenAI Responses API migration. Brain calls `POST http://proxy:{port}/api/multiturn` and receives a `ProxyResponse`, whose `tool_calls` and `response` fields are the same shape regardless of which provider sender proxy chose internally. `AgentLoop` does not need to know or care about the responses API; only proxy does.

## 2. Design

### 2.1 Core primitive

```python
# services/brain/app/agent/loop.py

from dataclasses import dataclass
from typing import AsyncIterator, Protocol
from shared.models.proxy import MultiTurnRequest, ProxyResponse


@dataclass(frozen=True)
class Budgets:
    max_iterations: int
    max_tool_calls: int
    timeout_seconds: int


@dataclass
class AgentResult:
    response: ProxyResponse          # the final proxy response that broke the loop
    iterations: int                  # how many proxy round-trips happened
    tool_calls_made: int             # total tool calls dispatched across all iterations
    status: str                      # "completed" | "max_iterations" | "max_tool_calls" | "timeout"


class ToolDispatcher(Protocol):
    async def __call__(self, name: str, arguments: dict) -> "ToolResponse": ...


class ProxyClient(Protocol):
    async def send(self, request: MultiTurnRequest) -> ProxyResponse: ...


class AgentLoop:
    """
    Stateless orchestration primitive that runs a proxy→tool→proxy loop
    until the model returns assistant content or a budget is exhausted.

    The loop owns no persistence. Side effects (ledger sync, trace logging)
    are expressed by yielding events; the caller handles them.
    """

    def __init__(
        self,
        *,
        proxy_client: ProxyClient,
        tool_dispatcher: ToolDispatcher,
        budgets: Budgets,
    ) -> None:
        self._proxy = proxy_client
        self._dispatch = tool_dispatcher
        self._budgets = budgets

    async def run(
        self,
        request: MultiTurnRequest,
    ) -> AsyncIterator["LoopEvent"]:
        """
        Async generator yielding events as the loop progresses.
        Terminates with a LoopTerminated event carrying the final AgentResult.
        Callers iterate the generator and persist as events arrive.
        """
        ...
```

### 2.2 Events

```python
# services/brain/app/agent/events.py

from dataclasses import dataclass
from typing import Any
from shared.models.proxy import ProxyResponse


@dataclass
class ProxyCallStarted:
    iteration: int
    request_messages_count: int


@dataclass
class ProxyCallCompleted:
    iteration: int
    response: ProxyResponse


@dataclass
class ToolCallRequested:
    iteration: int
    tool_call: dict                  # the raw tool_call dict from the proxy response
    tool_name: str
    arguments: dict


@dataclass
class ToolCallCompleted:
    iteration: int
    tool_call: dict
    tool_name: str
    arguments: dict
    result: Any                      # whatever call_tool returned, success or normalized error
    success: bool
    error: str | None


@dataclass
class AssistantMessageProduced:
    iteration: int
    content: str
    response: ProxyResponse


@dataclass
class LoopTerminated:
    result: "AgentResult"


LoopEvent = (
    ProxyCallStarted
    | ProxyCallCompleted
    | ToolCallRequested
    | ToolCallCompleted
    | AssistantMessageProduced
    | LoopTerminated
)
```

### 2.3 Invariants the loop maintains

- The loop mutates nothing the caller owns. It takes a `MultiTurnRequest`, produces a new one internally for each iteration by appending tool-call and tool-result messages, and never mutates the caller's object.
- The loop makes exactly one `proxy_client.send()` call per iteration.
- When the proxy response has `tool_calls`, the loop dispatches each one via `tool_dispatcher`, yields `ToolCallRequested` before dispatch and `ToolCallCompleted` after, then loops.
- When the proxy response has no `tool_calls` and non-empty `response`, the loop yields `AssistantMessageProduced` and terminates with `LoopTerminated(status="completed")`.
- Budget violations terminate with `LoopTerminated(status="max_iterations" | "max_tool_calls" | "timeout")` and a final `AgentResult` whose `response` is the last proxy response received (or `None` if the budget was hit before any proxy call completed).

### 2.4 Caller usage

```python
# pseudocode for multiturn.py after extraction

loop = AgentLoop(
    proxy_client=HttpProxyClient(port=proxy_port, timeout=TIMEOUT),
    tool_dispatcher=call_tool,
    budgets=Budgets(max_iterations=10, max_tool_calls=20, timeout_seconds=TIMEOUT),
)

final_response: ProxyResponse | None = None

async for event in loop.run(updated_request):
    match event:
        case ToolCallCompleted(tool_call=tc, result=r, success=s, error=e):
            await sync_tool_to_ledger(tc, r, platform=platform, model=message.model)
        case AssistantMessageProduced(content=c):
            await sync_assistant_to_ledger(c, platform=platform, model=message.model)
        case LoopTerminated(result=result):
            final_response = result.response
            if result.status != "completed":
                logger.warning("Agent loop terminated with status=%s", result.status)
```

The caller keeps ownership of ledger persistence. Sub-agent workers will use a *different* sink that writes to the trace table described in `Subagent_Design.md` §11 instead.

## 3. File Layout

New files:

- `services/brain/app/agent/__init__.py` — exports `AgentLoop`, `Budgets`, `AgentResult`, `LoopEvent`, `ProxyClient`, `ToolDispatcher`, and the event dataclasses.
- `services/brain/app/agent/loop.py` — the `AgentLoop` class.
- `services/brain/app/agent/events.py` — event dataclasses and the `LoopEvent` union.
- `services/brain/app/agent/proxy_client.py` — `HttpProxyClient` concrete implementation (async httpx call to `http://proxy:{port}/api/multiturn`).

Modified files:

- `services/brain/app/message/multiturn.py` — the loop body at lines 261-357 is replaced with an `AgentLoop` instantiation plus the `async for event in loop.run(...)` consumer. The persistence side effects (existing `/sync/tool` and `/sync/assistant` calls) move into small helper functions but stay in `multiturn.py` because they are caller-owned.

Out of scope for this doc:

- Extracting the pre/post-brainlet execution at `multiturn.py:206-258` and `multiturn.py:366-380`. The brainlet pipeline is a separate abstraction with its own concerns (topological sort, mode filtering, output merging). It stays in `multiturn.py` for this refactor.
- Extracting the ledger sync helpers into their own module. They stay inline for now.
- Extracting the fat `updated_request` assembly. Stays inline.

## 4. Types

All types are defined in `services/brain/app/agent/events.py` and `services/brain/app/agent/loop.py` as shown in §2. They are Python dataclasses, not Pydantic models — the loop is internal brain plumbing, not an HTTP contract, and dataclasses pattern-match cleanly.

`ToolResponse` already exists in `services/brain/app/tools/base.py`; `AgentLoop` imports it rather than redefining.

## 5. Behavior Preservation

The extracted loop must be behaviorally identical to the current `multiturn.py:261-357` for the top-level caller. Specifically:

| Current behavior | Preserved by |
|---|---|
| `max_iterations = 10` | `Budgets(max_iterations=10, ...)` in multiturn caller |
| Tool calls dispatched via `call_tool(fn, args_dict)` | `tool_dispatcher=call_tool` injection |
| Failed `json.loads` on tool args → `{"error": ...}` with loop continuing | Loop catches `JSONDecodeError`, yields `ToolCallCompleted(success=False, ...)`, continues |
| Assistant message appended to `updated_request.messages` after successful content | Loop's internal state accumulates messages the same way |
| Tool-call and tool-result messages appended (pair of `role=assistant tool_calls=[...]` and `role=tool tool_call_id=...`) | Loop's internal append logic is a direct port of the existing code |
| Per-iteration `httpx.AsyncClient` creation | `HttpProxyClient` creates one per `send()` call initially; connection pooling is a separate optimization |
| Ledger sync happens **between** tool calls and the next proxy call | Caller consumes events synchronously; by the time the next `ProxyCallStarted` event arrives, the caller has persisted all prior events |

The last row is the subtle one. The current code syncs each tool result to ledger *inside* the loop body, before continuing. The extracted version must ensure the caller's event handlers run to completion before the loop issues the next proxy call, otherwise a crash mid-loop would lose the sync. This is guaranteed by the `async for` contract: the generator is suspended until the consumer awaits the next iteration.

## 6. Acceptance Criteria

1. **Behavioral parity:** For a recorded fixture of a multi-turn conversation with tool calls, running the extracted `multiturn.py` produces the same final `ProxyResponse` as the pre-extraction version, and the same sequence of ledger `/sync/tool` and `/sync/assistant` POST bodies. Verified with a snapshot test using a mock proxy and mock tool dispatcher.

2. **Loop is importable in isolation:** `from app.agent import AgentLoop` succeeds with no FastAPI, no ledger client, no config file reads. Verified by a unit test that imports only `app.agent` in a clean test environment.

3. **Loop is testable in isolation:** A unit test can instantiate `AgentLoop` with a fake `ProxyClient` that returns a scripted sequence of `ProxyResponse` objects and a fake `ToolDispatcher` that returns scripted `ToolResponse` objects, and assert the event stream matches an expected sequence. No network, no filesystem, no database.

4. **Budgets are enforced:** A test that scripts 11 proxy responses each containing one tool call, with `Budgets(max_iterations=10, ...)`, must terminate with `LoopTerminated(status="max_iterations")` and `result.iterations == 10`. Similarly for `max_tool_calls`.

5. **Error handling parity:** Unparseable tool arguments produce a `ToolCallCompleted(success=False, error="Failed to parse tool arguments: ...")` event and the loop continues, matching current behavior at `multiturn.py:302-303`.

6. **No regression in `/api/multiturn`:** End-to-end smoke test — start brain service, send a realistic multiturn request with a tool call (e.g., `memory` search), confirm response and confirm the ledger was updated.

## 7. Implementation Order

1. **Create `services/brain/app/agent/events.py`** with all event dataclasses. No logic yet.
2. **Create `services/brain/app/agent/loop.py`** with the `AgentLoop` class. Port the loop body from `multiturn.py:261-357` line-by-line into `AgentLoop.run`, replacing direct httpx calls with `self._proxy.send()`, replacing `call_tool` calls with `self._dispatch`, and replacing inline ledger POSTs with event yields. Do not change semantics.
3. **Create `services/brain/app/agent/proxy_client.py`** with `HttpProxyClient` — a thin wrapper around the existing httpx logic at `multiturn.py:269-288`.
4. **Write unit tests** for `AgentLoop`: scripted proxy responses, scripted tool dispatcher, assert event sequence. Verify acceptance criteria #2, #3, #4, #5 pass.
5. **Modify `multiturn.py`** to consume `AgentLoop`:
   - Extract `sync_tool_to_ledger(...)` and `sync_assistant_to_ledger(...)` as local async helpers containing the existing sync bodies.
   - Replace `multiturn.py:261-357` with `AgentLoop` instantiation and the `async for event in loop.run(...)` consumer.
   - Keep the post-brainlet execution at `multiturn.py:366-380` unchanged.
6. **Run the end-to-end smoke test** (acceptance criterion #6) against the running brain container. Confirm ledger and response are unchanged.
7. **Commit the loop extraction as a single atomic change.** The new `agent/` module and the `multiturn.py` migration land together so there is no intermediate state where the loop is extracted but not called.

## 8. Non-Goals

- Changing the wire contract between brain and proxy.
- Changing `ProxyResponse` shape.
- Changing the brainlet system.
- Extracting the `updated_request` assembly into a typed `ContextPack`.
- Extracting `Mode` into a first-class domain type.
- Any sub-agent runtime work. That is a separate effort (phase 1 of `Subagent_Design.md`) and will consume this `AgentLoop` as a dependency.
- Connection pooling for the proxy client. If measured as a bottleneck later, `HttpProxyClient` is the one place to add it.

## 9. Interaction With Subagent_Design.md

See `docs/Subagent_Design.md` §24 "Implementation Note: Single Loop Layering" for how this primitive reframes the sub-agent runtime design. Summary: `subagents/runtime.py` becomes thinner than originally described — it configures `AgentLoop` with selected tools, phase-1 budgets, and a trace-writing event sink, and normalizes the final `AgentResult` into a `MinionResult`. It does not contain a second loop.
