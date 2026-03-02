# Kirishima CLI — Implementation Guide

## Status

- Author: Opus (based on Codex draft + discussion with Randi)
- Date: 2026-03-01
- Scope: Text-based terminal client for chatting with the agent, inspecting state, and debugging
- Replaces: `docs/CLI_Client_Design_and_Roadmap.md` (Codex draft — kept for reference)

---

## 1. What This Is

A local terminal client with two paths:

- **Chat path**: Send messages to the agent through the existing API service (`/v1/chat/completions`). After each response, pull the full exchange from ledger — including tool calls and tool results — and render the whole trace. This is the default view. You always see what the agent did, not just the final answer.
- **Admin path**: `/commands` go to a new admin endpoint on brain. Brain routes the command to the appropriate service, gets the result, and returns it. None of this touches ledger. It's out-of-band introspection and control.

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
  +-- starts with "/" --> Admin path
  |     CLI sends JSON-RPC call to brain POST /admin/rpc
  |     Brain dispatches to handler, which queries relevant services
  |     Brain returns result to CLI
  |     CLI renders result (never touches ledger)
  |
  +-- anything else --> Chat path
        CLI sends message to api POST /v1/chat/completions (via OpenAI SDK)
        (api forwards to brain /api/multiturn, brain does its thing)
        Response comes back through api
        CLI calls brain JSON-RPC (history.recent) to get full trace
        CLI renders: user message, tool calls, tool results, assistant response

The CLI only knows two endpoints:
  1. api service — /v1/chat/completions (OpenAI SDK)
  2. brain service — /admin/rpc (JSON-RPC)
```

### Key design decisions

- **The CLI only talks to two endpoints.** Chat goes to api (`/v1/chat/completions` via OpenAI SDK). Everything else goes to brain (`/admin/rpc` via JSON-RPC). The CLI has zero knowledge of ledger, proxy, scheduler, or any other service.
- **Brain is the gateway for all introspection.** Ledger is the source of truth for conversation history, but the CLI never talks to ledger directly. It asks brain via JSON-RPC (e.g., `history.recent`), and brain queries ledger and returns the data.
- **No session-local message buffer needed.** Ledger tracks conversation history. The CLI is stateless for chat — it sends a message, waits for the response, then asks brain for the trace.
- **Admin commands are synchronous request/response.** No async job IDs needed.
- **CLI never sends `user_id`.** Brain resolves the effective user internally using `get_admin_user_id()` from `app.util` for ledger-backed admin/history operations.

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

CLI flags: `--env-file` (path to `.env`, defaults to project root), `--api-port`, `--brain-port`

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
- As commands grow in complexity (memory management has lots of options, history has filters), the standard protocol scales without needing to evolve a bespoke envelope.
- MCP already uses JSON-RPC, so brain is already familiar territory.

### Brain-side example

```python
from jsonrpcserver import method, Result, Success, Error
from fastapi import Request

@method
async def memory_search(query: str, limit: int = 10) -> Result:
    # hit ledger, return results
    return Success({"memories": results})

@method
async def mode_get() -> Result:
    return Success({"mode": current_mode})

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

These are the admin commands to implement. **The specific endpoints and services each command hits are documented separately** — the implementing agent should look up the actual routes in each service's code and README.

### V1 — Core

| Command | Purpose |
|---------|---------|
| `/help` | List available commands (local, no network call) |
| `/exit` | Quit the CLI (local) |
| `/clear` | Clear the terminal (local) |
| `/services` | Show status of all services (health checks) |
| `/mode` | Get current LLM mode |
| `/mode <name>` | Set LLM mode |
| `/tools` | List available tools |
| `/context` | Show current context window / keyword scores |
| `/history [n]` | Show last N conversation turns from ledger (turn = user message + tool call/results + assistant response) |
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
- `cli/main.py` — argument parser (`argparse`) for `--api-url`, `--brain-url`, `--config`. Start a REPL loop that reads input, checks if it starts with `/`, and routes accordingly. For now, `/` commands just print "not implemented yet".
- `cli/client.py` — two clients: `openai.OpenAI` for chat, `jsonrpcclient` + `httpx` for admin commands. The CLI only ever talks to api and brain. See sections 4 and step 1.2 for examples.

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
- The CLI tracks the current mode in session state. Default comes from `.env` or by querying brain (`mode.get`) on startup. `/mode <name>` updates the session mode, which is used as the `model` parameter in subsequent chat requests.
- Display the response with basic formatting.
- At this point, chat works end-to-end without ledger rendering. This is the MVP checkpoint.

#### Step 1.3 — Ledger trace rendering

- After each chat response, call brain via JSON-RPC (`history.recent`) to get the full trace for the most recent turn. A turn is: user message + any tool calls/results + final assistant response. The CLI never talks to ledger directly — brain handles that.
- `cli/render.py` — format conversation entries by role:
  - `user` — plain text
  - `assistant` — highlighted/styled text
  - `tool` / `tool_call` — indented, dimmed, showing tool name + args/result summary
- Replace the basic "just show the response" display from 1.2 with the full trace view.
- If brain is unreachable for the trace query, fall back gracefully to just showing the direct API response (don't crash).

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
2. `mode.get` — return current mode
3. `mode.set` — set mode, return confirmation
4. `tools.list` — return available tools
5. `context.get` — return context window state
6. `heatmap.get` — return keyword heatmap
7. `history.recent` — return recent conversation turns (with tool calls/results grouped into each turn)
8. `memory.search` — search memories
9. `memory.get` — get a specific memory by ID
10. `memory.create` — create a new memory
11. `memory.edit` — update a memory's content
12. `memory.delete` — delete a memory
13. `memory.list` — list memories with optional filters
14. `history.delete_from` — delete all entries from a given row ID onward (truncate forward, preserves conversation structure)
15. `history.edit` — modify content of a specific entry (content only, not role/structure)

**Important**: Look up the actual service endpoints by reading each service's routes and README. Don't guess.

#### Step 2.3 — Wire CLI to admin endpoint

- `cli/commands.py` — command registry mapping `/command` strings to JSON-RPC method names + argument parsers. Parse `/mode claude` into `method="mode.set", params={"mode": "claude"}`. Parse `/memories medication` into `method="memory.search", params={"query": "medication"}`.
- `cli/client.py` — `send_admin(method, **params)` uses `jsonrpcclient` to call brain's `POST /admin/rpc`. See section 4 for the pattern.
- `cli/render.py` — render functions for each command type:
  - `services` → table with service name + status + response time
  - `mode` → single line showing current mode
  - `tools` → table of tool names and descriptions
  - `context` / `heatmap` → formatted keyword scores
  - `history` → conversation trace (reuse the renderer from Phase 1)
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

1. **Trace rendering**: The `history.recent` JSON-RPC method in brain should return *turns*, not raw rows. Response shape should be:
   - `turns`: list ordered newest-first
   - each turn contains:
     - `anchor_row_id`: row ID of the `user` row that starts the turn
     - `rows`: raw ledger rows in that turn (user/tool/assistant), each with original `row_id`
     - `summary`: optional compact line for list view
   - `count`: number of turns returned

   Turn grouping rule for single-user flow:
   - Start a new turn at each `role=user` row
   - Include all following `tool`/`tool_call` rows
   - End at next `assistant` row
   - If the most recent turn is incomplete (e.g., only user row), still return it as partial
   - Brain determines `user_id` internally via `get_admin_user_id()`; CLI does not pass user identifiers.

2. **History mutation endpoints (new in brain admin RPC)**:
   - These admin RPC methods require **new ledger HTTP endpoints**. Brain should proxy to ledger over HTTP; do not add direct DB access in brain.
   - Brain determines `user_id` internally via `get_admin_user_id()` from `app.util` before calling ledger.
   - Follow ledger's existing naming and file layout conventions (`services/ledger/app/routes/user.py` + `services/ledger/app/services/user/*`):
     - Route pattern should stay under the user message surface (`/user/{user_id}/...`)
     - Keep route handlers thin and push logic into service-layer helpers, matching current ledger style
   - `history.edit(row_id, content)`:
     - Validate row exists
     - Allow editing `user` and `assistant` rows only
     - Reject edits to `tool` / `tool_call` rows
     - Update content in ledger by row ID
     - Return edited row metadata + before/after preview
   - `history.delete_from(row_id)`:
     - Validate row exists
     - Delete all rows with `id >= row_id` for the single user
     - Return deleted row count and first deleted row ID
   - Both methods should return JSON-RPC errors with `data.service="ledger"` and status code details when ledger operations fail.

3. **Service health checks**: All services mount `/ping` via `shared/routes.py`. The `services` handler in brain should ping each known service and return the status map.
