# Kirishima CLI — Implementation Guide

## Status

- Author: Opus (based on Codex draft + discussion with Randi)
- Date: 2026-03-01
- Scope: Text-based terminal client for chatting with the agent, inspecting state, and debugging
- Replaces: `docs/CLI_Client_Design_and_Roadmap.md` (Codex draft — kept for reference)

### Current Progress (2026-03-08)

Completed:
- Textual split-pane CLI is active (`cli/tui.py`).
- Chat send path uses API `/v1/chat/completions` (OpenAI-compatible), mode selected client-side.
- Ledger preload at startup is implemented (no blank-slate startup).
- Live ledger stream is implemented via `GET /user/stream` (SSE), and transcript updates from ledger events.
- Tool activity is visible in transcript rendering (tool call + tool output).
- `/history [n]` is implemented in CLI and reloads recent turn-based history from ledger.

Not done yet:
- Brain `POST /admin/rpc` command path (JSON-RPC) is not implemented.
- CLI command registry + admin command routing from this guide is not implemented.
- Service introspection/admin commands (`/services`, `/tools`, `/memory ...`, `/context`, `/heatmap`, etc.) are not implemented.
- Reconnect catch-up/resume behavior for ledger stream is not implemented.

Notes:
- Current implementation intentionally connects CLI directly to ledger (default `http://localhost:4203`) for history/streaming.
- `/mode` remains client-local session behavior by design.

---

## 1. What This Is

A local terminal client with three paths:

- **Chat path**: Send messages to the agent through the existing API service (`/v1/chat/completions`).
- **History path**: Preload history, `/history`, and live transcript streaming come directly from ledger. This is intentional. Ledger is the source of truth, and there is no benefit in making brain proxy history/stream events just to forward them again.
- **Admin path**: Introspection and cross-service control commands go to a new admin endpoint on brain. Brain routes the command to the appropriate service, gets the result, and returns it. This is out-of-band control, not conversation history transport.

The separation is about what enters the conversation thread and what doesn't. Checking the heatmap shouldn't pollute the agent's context. Searching memories for debugging shouldn't create a ledger entry.

Operational assumptions for this system:
- Single-user deployment
- One active client session at a time (no concurrent clients/background writers)

### Non-goals

- Replacing OpenWebUI as the primary chat UI
- Becoming a microservice
- Streaming (disabled system-wide, can be added later)
- Real-time tool call visibility during execution (ledger after-the-fact is sufficient)
- Config mutation workflows (just use the config file + git)
- Codex delegation (future, not part of this design)

---

## 2. Architecture

```
User input
  |
  +-- starts with "/" --> Command path
  |     +-- local command (/help, /clear, /exit, /mode)
  |     |     CLI handles it locally
  |     |
  |     +-- history command (/history ...)
  |     |     CLI calls ledger directly
  |     |
  |     +-- admin command (/services, /tools, /memory ..., /context, /heatmap, ...)
  |           CLI sends JSON-RPC call to brain POST /admin/rpc
  |           Brain dispatches to handler, which queries relevant services
  |           Brain returns result to CLI
  |
  +-- anything else --> Chat path
        CLI sends message to api POST /v1/chat/completions (via OpenAI SDK)
        (api forwards to brain /api/multiturn, brain does its thing)
        Response comes back through api
        Ledger records the turn
        CLI transcript updates from direct ledger preload/stream/history calls

The CLI knows three endpoint families:
  1. api service — /v1/chat/completions (OpenAI SDK)
  2. ledger service — history preload, /user/stream, /user/{user_id}/messages
  3. brain service — /admin/rpc (JSON-RPC)
```

### Key design decisions

- **The CLI talks to api, ledger, and brain.** This is deliberate, not architectural drift. Each path maps cleanly to the service that already owns that behavior.
- **Ledger is the direct history/stream source.** The CLI should connect straight to ledger for preload, `/history`, and SSE. Brain should not proxy history or stream events unless it is adding real behavior beyond transport.
- **Brain is the gateway for admin orchestration.** Use brain for commands that need cross-service routing, aggregation, or policy, not as a pass-through for ledger history reads.
- **`/mode` is local session state.** The active chat mode for the CLI session is chosen client-side and sent as the `model` field on chat requests. It is not an admin endpoint command.
- **No session-local message buffer needed.** Ledger tracks conversation history. The CLI remains stateless for chat transport even though it reads transcript/history directly from ledger.
- **Admin commands are synchronous request/response.** No async job IDs needed.
- **CLI may need `user_id` for direct ledger history access.** This is acceptable for the host-run single-user CLI. Brain should still resolve the effective user internally for admin operations that need it.

---

## 3. Repository Layout

```
cli/
  __init__.py
  main.py          # Entry point, REPL loop, input routing (chat vs /command)
  client.py        # HTTP client — openai SDK for chat, jsonrpcclient for admin
  commands.py      # Command registry, parser, argument handling
  render.py        # Output formatting — conversation traces, tables, error cards
  config.py        # Load ~/.kirishima/config.json, env overrides, CLI flags
```

Launch: `python -m cli.main`

CLI flags: `--env-file` (path to `.env`, defaults to project root), `--api-port`, `--brain-port`, `--ledger-port`

Config resolution priority: CLI flags > env vars > `.env` file > hardcoded defaults

---

## 4. Admin Path — JSON-RPC

The admin path uses **JSON-RPC 2.0** over HTTP. This is the same protocol MCP already uses internally, and there are mature Python libraries for both sides.

- **Brain (server)**: Use `jsonrpcserver` to register method handlers. It integrates with FastAPI — a single `POST /admin/rpc` endpoint that dispatches to registered methods.
- **CLI (client)**: Use `jsonrpcclient` to make calls. Handles request IDs, error parsing, and batch requests automatically.

### Wire format

```json
// Request
{"jsonrpc": "2.0", "method": "memory.search", "params": {"query": "medication schedule"}, "id": "uuid"}

// Success response
{"jsonrpc": "2.0", "result": {"memories": [...]}, "id": "uuid"}

// Error response
{"jsonrpc": "2.0", "error": {"code": -32603, "message": "ledger request failed", "data": {"service": "ledger", "status_code": 502}}, "id": "uuid"}
```

### Why JSON-RPC instead of a custom envelope

- The custom envelope we originally designed was JSON-RPC with different field names. Just use the real thing.
- `jsonrpcserver` gives you method dispatch, argument validation, and standard error codes — that's the command registry and dispatcher for free.
- `jsonrpcclient` gives the CLI typed requests and error handling without custom `schemas.py` models.
- As commands grow in complexity (memory management, service inspection, scheduler control), the standard protocol scales without needing to evolve a bespoke envelope.
- MCP already uses JSON-RPC, so brain is already familiar territory.

### Brain-side example

```python
from jsonrpcserver import method, Result, Success, Error
from fastapi import Request

@method
async def memory_search(query: str, limit: int = 10) -> Result:
    # hit ledger, return results
    return Success({"memories": results})

# FastAPI route
@router.post("/admin/rpc")
async def admin_rpc(request: Request):
    body = await request.body()
    response = await dispatch(body)
    return Response(str(response), media_type="application/json")
```

### CLI-side example

```python
from jsonrpcclient import request_json, parse
import httpx

async def send_admin(method: str, **params):
    req = request_json(method, params=params)
    resp = await httpx.AsyncClient().post(brain_url + "/admin/rpc", content=req)
    return parse(resp.json())
```

---

## 5. Command List

These are the CLI commands to support. Commands under the admin path should be implemented through brain `POST /admin/rpc`. **The specific endpoints and services each command hits are documented separately** — the implementing agent should look up the actual routes in each service's code and README.

### V1 — Core

| Command | Purpose |
|---------|---------|
| `/help` | List available commands (local, no network call) |
| `/exit` | Quit the CLI (local) |
| `/clear` | Clear the terminal (local) |
| `/mode` | Show current CLI session mode (local) |
| `/mode <name>` | Set current CLI session mode (local) |
| `/history [n]` | Show last N conversation turns from ledger (direct ledger call, not brain admin RPC) |
| `/services` | Show status of all services (health checks) |
| `/tools` | List available tools |
| `/context` | Show current context window / keyword scores |
| `/history delete-from <row_id>` | Delete everything from this row ID onward (inclusive). Truncates forward — keeps conversation structure intact. Use `/history` first to see row IDs. |
| `/history edit <row_id> <text>` | Modify the content of a specific entry (content only, doesn't change role or structure) |
| `/heatmap` | Show keyword heatmap state |
| `/memory search <query>` | Search memories |
| `/memory get <id>` | View a specific memory by ID |
| `/memory create <text>` | Create a new memory (with optional flags for category, keywords, etc.) |
| `/memory edit <id> <text>` | Update a memory's content |
| `/memory delete <id>` | Delete a memory |
| `/memory list [--category X]` | List memories, optionally filtered |
| `/last-error` | Re-display the last error (local, cached from previous command) |

### V2 — When V1 is solid

| Command | Purpose |
|---------|---------|
| `/scheduler list` | List scheduled jobs |
| `/scheduler pause <id>` | Pause a scheduled job |
| `/scheduler resume <id>` | Resume a scheduled job |
| `/scheduler delete <id>` | Delete a scheduled job |
| `/stickynotes [query]` | View/search sticky notes |
| `/contacts [query]` | Search contacts |
| `/logs <service> [lines]` | Pull recent docker logs for a service |

---

## 6. Implementation Phases

### Phase 1: Skeleton + Chat Path

**Goal**: You can type a message, get a response, and see the full conversation trace including tool calls.

#### Step 1.1 — Project structure

- Create the `cli/` directory with all files from section 3
- `cli/__init__.py` — empty
- `cli/config.py` — load the `.env` file from the project root to get service ports (same `.env` Docker uses). All connections are `localhost:<port>`. Fall back to env vars if `.env` isn't found. Fall back to hardcoded default ports as a last resort.
- `cli/main.py` — argument parser (`argparse`) for `--api-url`, `--brain-url`, `--ledger-url`, `--env-file`, and related port overrides. Start a REPL loop that reads input, checks if it starts with `/`, and routes accordingly. For now, `/` commands just print "not implemented yet".
- `cli/client.py` — clients for chat (`openai.OpenAI` to api), history/streaming (`httpx` to ledger), and admin commands (`jsonrpcclient` + `httpx` to brain).

#### Step 1.2 — Chat send/receive

- The api service is an **OpenAI-compatible endpoint**. Use the official `openai` Python SDK (`pip install openai`) pointed at the local api service URL as the `base_url`. Do not hand-roll HTTP calls for the chat path.
  ```python
  from openai import OpenAI
  client = OpenAI(base_url="http://localhost:<api_port>/v1", api_key="not-needed")
  response = client.chat.completions.create(
      model="<current mode or default>",
      messages=[{"role": "user", "content": "<user input>"}]
  )
  ```
- Extract the assistant message from `response.choices[0].message.content` and token usage from `response.usage`.
- The CLI tracks the current mode in session state. Default comes from `.env`/config at startup. `/mode <name>` updates the session mode locally, which is then used as the `model` parameter in subsequent chat requests.
- Display the response with basic formatting.
- At this point, chat works end-to-end without ledger rendering. This is the MVP checkpoint.

#### Step 1.3 — Ledger trace rendering

- Use ledger directly for transcript preload, `/history`, and live SSE updates. A turn is: user message + any tool calls/results + final assistant response.
- `cli/render.py` — format conversation entries by role:
  - `user` — plain text
  - `assistant` — highlighted/styled text
  - `tool` / `tool_call` — indented, dimmed, showing tool name + args/result summary
- Replace the basic "just show the response" display from 1.2 with the full trace view.
- If ledger is unreachable for preload/history/streaming, fall back gracefully to just showing the direct API response path and local status/error messages.

#### Step 1.4 — Basic REPL polish

- Input prompt: something like `you> ` for chat
- Handle Ctrl+C (cancel current input, don't exit) and Ctrl+D (exit)
- Handle empty input (ignore, re-prompt)
- Show request duration after each chat message (wall clock time from send to response)
- `/clear` clears terminal
- `/exit` exits cleanly
- `/help` prints the command list

---

### Phase 2: Admin Endpoint + Core Commands

**Goal**: Brain has a `/admin/rpc` endpoint. CLI can query system state without polluting conversation history.

#### Step 2.1 — Brain admin endpoint

- Install `jsonrpcserver` in brain's requirements.txt
- Add `POST /admin/rpc` to brain using the pattern from section 4
- Register method handlers using `@method` decorator — one function per command
- Each handler receives typed arguments directly (JSON-RPC handles dispatch and validation)
- Return `Success(result_dict)` or `Error(code, message, data)` — the library handles the envelope
- No custom Pydantic admin models needed — JSON-RPC is the contract

#### Step 2.2 — Implement V1 admin command handlers in brain

Implement each command handler one at a time. Each handler:
1. Parses its args
2. Makes HTTP call(s) to the relevant service(s)
3. Returns a normalized result dict

Commands to implement (in priority order):
1. `services` — health check all services, return status map
2. `tools.list` — return available tools
3. `context.get` — return context window state
4. `heatmap.get` — return keyword heatmap
5. `memory.search` — search memories
6. `memory.get` — get a specific memory by ID
7. `memory.create` — create a new memory
8. `memory.edit` — update a memory's content
9. `memory.delete` — delete a memory
10. `memory.list` — list memories with optional filters

Not part of brain admin RPC:
- `/mode` and `/mode <name>` remain local CLI commands
- `/history [n]` remains a direct ledger read
- live transcript streaming remains a direct ledger SSE connection

**Important**: Look up the actual service endpoints by reading each service's routes and README. Don't guess.

#### Step 2.3 — Wire CLI to admin endpoint

- `cli/commands.py` — command registry mapping only admin `/command` strings to JSON-RPC method names + argument parsers. Local commands (`/help`, `/clear`, `/exit`, `/mode`) and direct-ledger history commands stay outside this path.
- `cli/client.py` — `send_admin(method, **params)` uses `jsonrpcclient` to call brain's `POST /admin/rpc`. See section 4 for the pattern.
- `cli/render.py` — render functions for each command type:
  - `services` → table with service name + status + response time
  - `tools` → table of tool names and descriptions
  - `context` / `heatmap` → formatted keyword scores
  - `memories` → list of memory entries with scores
- `/last-error` — cache the last error response locally, re-display on demand

#### Step 2.4 — Error handling

- Every admin call wraps in try/except
- Network errors (brain unreachable) → clear message, no stack trace
- JSON-RPC errors → render the error card (code, message, data.service, data.status_code)
- All errors cached for `/last-error`

---

### Phase 3: Polish + V2 Commands

**Goal**: CLI is genuinely useful for daily debugging. Add remaining commands.

#### Step 3.1 — Textual TUI (optional but recommended)

If you want the split-pane experience (status panel on top, input on bottom), this is where `textual` comes in. This is optional — the REPL from phases 1-2 is fully functional without it. But if you want:
- Top pane: scrollable output (conversation trace + command results)
- Bottom pane: input box
- Status bar: current mode, last request duration, error indicator
- Keyboard shortcuts: Ctrl+L clear, up arrow for history

#### Step 3.2 — V2 commands

Add command handlers in brain for:
- `scheduler.list`, `scheduler.pause`, `scheduler.resume`, `scheduler.delete`
- `stickynotes.search`
- `contacts.search`
- `logs.docker` (if CLI runs on the host, it can pull docker logs directly without going through brain — design decision)

#### Step 3.3 — Quality of life

- Command tab-completion (if using textual or prompt_toolkit)
- Input history (up/down arrow)
- Colorized output (rich or textual built-ins)
- Configurable output verbosity (e.g., hide tool calls by default, show with `--verbose` or a toggle command)

---

## 7. Dependencies

```
openai         # official OpenAI SDK — chat path (api service is OpenAI-compatible)
jsonrpcclient  # JSON-RPC client — admin path (CLI side)
jsonrpcserver  # JSON-RPC server — admin path (brain side)
httpx          # async HTTP client — transport for jsonrpcclient
python-dotenv  # read .env file for port config
pydantic       # request/response models (already used across project)
rich           # terminal formatting, tables, syntax highlighting (for REPL mode)
textual        # TUI framework (optional, for Phase 3 split-pane mode)
prompt_toolkit # input handling, history, completion (alternative to textual for REPL)
```

Start with `openai`, `jsonrpcclient`, `httpx`, `python-dotenv`, and `rich`. `jsonrpcserver` goes in brain's requirements. Add `textual` or `prompt_toolkit` only if/when you get to Phase 3.

---

## 8. What Not to Build

- **Config mutation workflows** — editing config is a text editor + git problem, not a CLI feature
- **Codex delegation** — future idea, not part of this
- **Streaming** — disabled system-wide, add later if enabled
- **Session-local message buffer** — ledger is the source of truth
- **Graylog integration** — nice to have someday, not now
- **Auth** — trusted local network, add later if needed

---

## 9. Notes for the Implementor

1. **History and streaming are direct ledger concerns**:
   - Keep transcript preload, `/history`, and live SSE against ledger.
   - Do not add `history.recent` to brain admin RPC just to proxy ledger rows.
   - Do not route ledger stream traffic through brain unless brain is adding actual transformation or policy.

2. **History mutation already exists in ledger**:
   - Ledger already has endpoints for edit/delete-from under the user message surface.
   - If the CLI exposes `/history edit` or `/history delete-from`, prefer calling ledger directly unless there is a concrete reason to centralize those mutations behind brain.
   - Do not add direct DB access in CLI or brain.

3. **Service health checks**: All services mount `/ping` via `shared/routes.py`. The `services` handler in brain should ping each known service and return the status map.
