# Sub-Agent Design

This document describes a concrete sub-agent architecture for Kirishima.

Related short doc:
- `docs/Subagent_Architecture_Overview.md`

## 1. Goals

The sub-agent system should solve these problems:

- reduce the number of tools exposed directly to the top-level conversational LLM
- keep retrieval-heavy or multi-step tasks out of the main context window
- support narrow, bounded delegation for research, history lookup, and external actions
- provide a clean place to integrate external executors such as Codex
- scale to larger tool inventories, including MCP-backed tools

## 2. Constraints

- no recursive multi-agent framework in phase 1
- no bypassing `proxy` as the LLM gateway
- no replacement of existing service boundaries

## 3. Current State In Repo

Relevant current pieces:

- `services/brain/app/message/multiturn.py`
  - main orchestration path
  - assembles tool list
  - handles tool loop
- `services/brain/app/tools/router.py`
  - cheap LLM-based router that selects relevant tools from a catalog
- `services/brain/app/tools/__init__.py`
  - registry and dispatch for local tools
  - fallthrough to external MCP servers
- `services/brain/app/routes/mcp.py`
  - exposes brain tools as MCP endpoints
- `services/brain/app/routes/admin.py`
  - already provides a small JSON-RPC admin surface
- `docs/Memory_System_Current_State_And_Proposal.md`
  - already establishes the idea that history retrieval should go through a sub-agent and return only the relevant slice

Kirishima already has most of the supporting plumbing. What is missing is the worker runtime and the change in top-level tool philosophy.

## 4. Architecture Summary

The proposed model is:

- top-level conversational agent acts as supervisor
- top-level tool surface is reduced to one or two tools
- `brain` owns sub-agent orchestration
- worker agents first select tools from a menu, then execute with only the selected tools
- workers execute under hard budgets
- workers return a minimal payload to the supervisor

Recommended top-level tools:

- `spawn_minion`
- `create_memory` or equivalent explicit memory-write tool

Everything else moves behind the worker boundary.

## 5. Top-Level Tool Contract

### 5.1 `spawn_minion`

Top-level tool visible to the conversational LLM.

Suggested OpenAI tool schema:

```json
{
  "type": "function",
  "function": {
    "name": "spawn_minion",
    "description": "Delegate a bounded multi-step task to a worker agent and return a concise result.",
    "parameters": {
      "type": "object",
      "properties": {
        "task": {
          "type": "string",
          "description": "Natural-language description of the task to delegate."
        }
      },
      "required": ["task"],
      "additionalProperties": false
    }
  }
}
```

The public interface stays small.

### 5.2 Explicit Memory Write Tool

Keep memory authoring separate from generic delegation.

## 6. Internal Execution Envelope

Internal model:

```python
class MinionRequest(BaseModel):
    task: str
    max_iterations: int
    max_tool_calls: int
    timeout_seconds: int
    allow_child_agents: bool = False
    selected_capabilities: list[str]
```

`brain` can infer them from:

- the natural-language task
- the worker's tool-selection pass
- hardcoded system safety rails

## 7. Phase 1 Tool Selection

- show tool menu
- request needed tools by name
- load only those tools
- run worker

If the menu gets too large later, group it by MCP server.

## 8. Tool Menu

Phase 1 uses a selection pass followed by an execution pass:

1. show the worker a plaintext tool menu
2. ask the worker which tools it needs
3. load only those tools for the execution pass

### 8.1 Tool Menu Shape

The model-facing tool list is plaintext.

Suggested menu shape:

```text
Available tools:
- history_search: Search summaries and optionally transcript history for a specific fact or excerpt.
- web_fetch: Retrieve information from the web.
- memory_create: Create a memory with explicit keywords.
```

The code can store tool metadata however it wants internally.

### 8.2 Selection Fallback

If tool selection fails:

- write a `capability_gaps` row if the worker asked for something nonexistent
- otherwise fail fast or fall back conservatively

## 9. Worker Lifecycle

Phase 1 lifecycle:

1. top-level LLM calls `spawn_minion(task=...)`
2. `brain` creates a worker request envelope
3. `brain` gives the worker a plaintext tool menu
4. worker returns the tool names it wants
5. if a requested tool does not exist, `brain` writes a `capability_gaps` row
6. `brain` constructs an execution prompt with:
   - task
   - budgets
   - only the selected tools
7. `brain` sends the execution request through `proxy`
8. worker performs its own tool loop under hard limits
9. worker returns a minimal result payload
10. `brain` writes richer execution details to ledger trace storage
11. `brain` converts the minimal result into the top-level tool output
12. top-level LLM uses that result in the conversation

## 10. Supervisor-Facing Result Payload

The returned payload to the main conversational agent is tiny.

Suggested phase 1 response:

```python
class MinionResult(BaseModel):
    ok: bool
    response: str | None = None
    error: str | None = None
    needs_clarification: str | None = None
```

The supervisor does not need:

- raw tool outputs
- source lists
- structured artifacts
- internal worker state
- execution trace metadata

That information belongs in internal logging or ledger trace storage.

### 10.1 Success

Example:

```json
{
  "ok": true,
  "response": "The endpoint requires OAuth2 and returns paginated results."
}
```

### 10.2 Failure

Example:

```json
{
  "ok": false,
  "error": "Max tool call budget exceeded."
}
```

### 10.3 Clarification Needed

Example:

```json
{
  "ok": false,
  "needs_clarification": "Do you want me to search summaries only, or summaries plus transcript history?"
}
```

## 11. Internal Trace Logging

The worker runtime can produce rich internal data. Log it to ledger in a separate trace table or equivalent structure.

Suggested trace contents:

- sub-agent id
- parent conversation or tool-call id
- menu shown to worker
- selected tools
- iteration count
- raw tool calls and outputs
- timing
- source references
- final worker status

The supervisor-facing payload stays small.

## 12. Missing Capability Feedback

Write a simple ledger row when the conversational agent or worker asks for a tool or feature that does not exist yet.

Suggested table shape:

- `id`
- `created_at`
- `requested_task`
- `failure_reason`
- `context_excerpt`

Optional field:

- `source`

This is meant for manual inspection with a basic query like:

```sql
select * from capability_gaps order by created_at desc;
```

If a row is useless, ignore it or delete it.

## 13. Budgets And Limits

Workers need hard budgets.

Suggested phase 1 defaults:

- `max_iterations = 6`
- `max_tool_calls = 8`
- `timeout_seconds = 45`
- `allow_child_agents = false`

### Hard Rule

Phase 1 workers do not spawn child workers.

## 14. Tool Visibility Model

### 14.1 Top-Level Supervisor Visibility

The top-level conversational model should see:

- `spawn_minion`
- explicit memory-write capability
- maybe a very small set of truly universal tools if proven necessary

It should not see the whole global registry.

### 14.2 Worker Visibility

Workers see only:

- the tool menu during the selection pass
- only the selected tools during the execution pass
- tools allowed by client/security rules

This is a strict subset model.

## 15. History Search As First-Class Worker Use Case

The memory proposal already points in this direction. Recommended behavior:

- main conversational agent asks a worker to retrieve some prior fact or excerpt
- worker gets `history_search`
- worker searches summaries first
- worker optionally searches transcript in deep mode
- worker returns only the relevant answer or excerpt to the supervisor
- source references can still be recorded in the internal trace

This keeps raw transcript out of the main conversation context.

## 16. Codex Integration

Codex and sub-agents are loosely coupled.

- `brain` owns the sub-agent framework
- Codex is one optional worker backend or delegated capability

Treat Codex as one capability option, likely behind a later coding-oriented path or some research scenarios.

If Codex can be exposed as an MCP server, that is a good fit because Kirishima already has:

- an MCP client path for external servers
- an MCP server path for exposing tools

That would let the worker request a Codex-backed tool from the menu without making the top-level architecture care how Codex is wired.

## 17. Where This Fits In `brain`

### 17.1 `multiturn.py`

`services/brain/app/message/multiturn.py` is still the main top-level orchestration path.

The likely evolution is:

- remove most direct user-facing tools from top-level tool assembly
- replace them with `spawn_minion` and memory write
- keep the top-level loop, but expect most substantive work to happen inside the worker tool

### 17.2 New Internal Modules

Suggested additions:

- `services/brain/app/subagents/__init__.py`
- `services/brain/app/subagents/models.py`
- `services/brain/app/subagents/selection.py`
- `services/brain/app/subagents/prompts.py`
- `services/brain/app/subagents/runtime.py`
- `services/brain/app/subagents/logging.py`
- `services/brain/app/tools/spawn_minion.py`

Possible responsibilities:

- `models.py`
  - request/result envelope models
- `selection.py`
  - build plaintext tool menu
  - parse requested tool names
- `prompts.py`
  - worker prompts for selection pass and execution pass
- `runtime.py`
  - worker execution loop with budgets
- `logging.py`
  - sub-agent trace persistence to ledger
  - missing-capability row writes
- `spawn_minion.py`
  - top-level tool wrapper that calls runtime

## 18. Suggested Worker Runtime Flow

Pseudo-flow:

```text
spawn_minion tool called
  -> build MinionRequest from task
  -> show plaintext tool menu
  -> get requested tool names
  -> if requested tool does not exist, write capability_gaps row
  -> build execution prompt with selected tools only
  -> call proxy /api/multiturn with worker messages + selected tools
  -> execute worker tool loop with limits
  -> write rich execution trace to ledger
  -> normalize supervisor-facing output to MinionResult
  -> return MinionResult as spawn_minion tool result
```

The worker can reuse the same general proxy/tool-call mechanics as top-level chat.

## 19. Logging And Persistence

### Phase 1 Recommendation

Persist:

- top-level `spawn_minion` invocation
- worker trace data in a separate ledger structure
- simple missing-capability rows in `capability_gaps`
- minimal supervisor-facing result
- error/failure state

Do not automatically persist:

- the worker's full internal scratchpad
- giant intermediate retrieval payloads
- every planning artifact unless debugging explicitly needs it

- rich trace for debugging and audit
- dumb gap rows for feature feedback
- tiny returned payload for the conversational agent

## 20. Failure Handling

Rules:

- selection failure should degrade conservatively or fail cleanly
- tool failure inside a worker should be returned in normalized form
- budget exhaustion should return a worker failure, not hang
- invalid worker output should be normalized into a failure result

Suggested failure shape:

```json
{
  "ok": false,
  "error": "Max tool call budget exceeded."
}
```

## 21. Recommended Implementation Phases

### Phase 1: Introduce Basic Worker Runtime

- add `spawn_minion` tool
- add internal worker request/result models
- implement tool-selection pass
- implement execution pass with selected tools only
- implement worker execution loop with hard limits
- add sub-agent trace persistence
- add simple `capability_gaps` persistence
- keep `allow_child_agents = false`

### Phase 2: Move Retrieval Use Cases Behind Workers

- add `history_search` if not already present
- route history lookup through `spawn_minion`
- keep retrieval responses narrow at the supervisor boundary

### Phase 3: Reduce Top-Level Tool Surface

- remove most direct tools from top-level multiturn exposure
- leave only `spawn_minion` plus memory write
- keep specialty tools internal to workers

### Phase 4: Add External Executor Integrations

- integrate Codex as MCP-backed or equivalent delegated capability
- expose it through the tool menu
- keep top-level chat model unaware of low-level executor details

### Phase 5: Reevaluate Controlled Child Delegation

Only after the single-worker path is stable:

- allow certain worker paths to spawn child workers
- enforce shallower, stricter budgets
- do this only if real workloads prove it necessary

## 22. Decisions

### Decisions

- one natural-language delegation tool at the top level
- structured internal runtime
- minimal supervisor-facing payload
- missing capabilities stored in SQLite, not just logs
- no child workers in phase 1
- Codex stays an optional backend capability
- workers use a menu in the selection pass and a reduced tool set in the execution pass

## 23. Final Recommendation

Build the first version around:

- one top-level delegation tool
- one explicit memory-write tool
- one worker depth
- a plaintext tool menu
- a selection pass
- an execution pass with selected tools only
- hard budgets
- minimal supervisor-facing payloads
- richer internal ledger traces
- a dumb `capability_gaps` table for feature feedback

That is enough to solve the immediate architecture problem without vanishing into agent-framework nonsense.

## 24. Implementation Note: Single Loop Layering

This section is an addendum to the original design. It was added after a separate refactor pass identified that §17 and §18 — as written — implicitly describe two parallel tool loops: the existing one in `services/brain/app/message/multiturn.py:261-357`, and a new one inside the proposed `services/brain/app/subagents/runtime.py`. Any future change to the loop (streaming, cancellation, trace shape, the OpenAI Responses API migration, budget enforcement) would have to land in both places and the two would drift.

The layering this document now assumes is: **there is one shared loop primitive, and both the top-level supervisor and the worker runtime are callers.**

The loop primitive is described in detail in `docs/AgentLoop_Extraction.md`. It lives at `services/brain/app/agent/loop.py` as `AgentLoop`, takes injected `ProxyClient`, `ToolDispatcher`, and `Budgets`, and emits an async stream of events (`ProxyCallStarted`, `ToolCallRequested`, `ToolCallCompleted`, `AssistantMessageProduced`, `LoopTerminated`) that the caller consumes and persists.

### 24.1 Effect on §17.1 (`multiturn.py` evolution)

§17.1 says "keep the top-level loop, but expect most substantive work to happen inside the worker tool." Under the single-loop layering, "the top-level loop" is not a fixed artifact — it is `multiturn.py`'s *caller code* around `AgentLoop.run(...)`. That caller code still exists and still owns top-level concerns (brainlet execution, ledger persistence, agent prompt assembly, tool routing via `router.py`). But the iteration/dispatch mechanics are no longer inline in `multiturn.py`.

### 24.2 Effect on §17.2 (new internal modules)

The suggested module list in §17.2 still stands with one adjustment:

- `services/brain/app/subagents/runtime.py` — **thinner than originally described**. It no longer contains a worker execution loop. Instead it:
  1. Configures an `AgentLoop` instance with the worker's `selected_capabilities` as the `ToolDispatcher` scope, the phase-1 budgets from §13 (`max_iterations=6`, `max_tool_calls=8`, `timeout_seconds=45`), and a `ProxyClient` identical to the top-level one.
  2. Consumes the `AgentLoop` event stream with a *trace-writing* event handler that persists to the ledger trace table described in §11 (sub-agent id, menu shown, selected tools, iteration count, raw tool calls, timing).
  3. On `LoopTerminated`, normalizes the final `AgentResult` into a `MinionResult` per §10. Budget-exhaustion statuses (`max_iterations`, `max_tool_calls`, `timeout`) map to `MinionResult(ok=false, error=...)`.
  4. Writes the minimal supervisor-facing `MinionResult` as the `spawn_minion` tool output.

The other modules (`models.py`, `selection.py`, `prompts.py`, `logging.py`, `spawn_minion.py`) are unchanged from §17.2.

### 24.3 Effect on §18 (worker runtime flow)

The pseudo-flow in §18 is still correct at the description level. The single line that changes is:

> execute worker tool loop with limits

That step is now: `async for event in AgentLoop(...).run(execution_request): trace_sink.handle(event)`. The loop mechanics are not the worker runtime's responsibility.

### 24.4 Effect on §13 (budgets)

Budgets in §13 (`max_iterations`, `max_tool_calls`, `timeout_seconds`, `allow_child_agents`) map directly onto the `Budgets` dataclass from `docs/AgentLoop_Extraction.md` §2.1 — except for `allow_child_agents`, which is a concern of the `ToolDispatcher` (whether `spawn_minion` is in the dispatcher's allowed tool set) rather than the loop itself. In phase 1, the worker's `ToolDispatcher` simply does not include `spawn_minion`, enforcing the "no child workers" rule at the capability-filter boundary.

The top-level `multiturn.py` caller also gets a `Budgets` object instead of the current unnamed magic number `max_iterations = 10` at `multiturn.py:264`. Budget parity is a free side benefit of the extraction.

### 24.5 Effect on the responses API migration

None. The `AgentLoop` primitive only touches `ProxyResponse` (`tool_calls` and `response` fields) and only calls `POST /api/multiturn` on proxy. The OpenAI Responses API migration lives entirely inside proxy and is invisible to `AgentLoop` and to this design. The two efforts can land in either order.

### 24.6 Implementation sequence

1. Extract `AgentLoop` per `docs/AgentLoop_Extraction.md` (prerequisite).
2. Land phase 1 of this document with `subagents/runtime.py` as a thin `AgentLoop` caller.
3. Subsequent phases (2-5) are unchanged.

Do not begin phase 1 of this document until `AgentLoop` exists, or the subagent runtime will duplicate the loop and have to be rewritten to consume `AgentLoop` afterwards.
