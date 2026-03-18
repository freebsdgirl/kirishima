# Brain Service

Central orchestrator for the Kirishima system. Routes messages, manages context, executes tools, runs brainlets, and coordinates all other services. Never talks to LLMs directly — always goes through proxy. Runs on `${BRAIN_PORT}`.

## Endpoints

### Core Processing

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/multiturn` | Primary conversation orchestration (context, tools, brainlets, tool loop) |
| POST | `/api/singleturn` | Simple passthrough to proxy (no tools, no brainlets) |

### Mode Management

| Method | Path | Description |
|--------|------|-------------|
| POST | `/mode/{mode}` | Set active model mode |
| GET | `/mode` | Get current mode |

### Admin

| Method | Path | Description |
|--------|------|-------------|
| POST | `/admin/rpc` | JSON-RPC admin/introspection endpoint for CLI commands |

Supported JSON-RPC methods:

| Method | Params | Result |
|--------|--------|--------|
| `tools.list` | `{}` | Registered tool metadata (`name`, `description`, `always`, `persistent`, `clients`) |
| `context.get` | `{"limit": <positive int>}` | Current contextual memories plus keyword scores |
| `heatmap.get` | `{}` | Current keyword heatmap scores |

### Notifications

| Method | Path | Description |
|--------|------|-------------|
| POST | `/notification` | Create a notification |
| GET | `/notification/{user_id}` | Get pending notifications for a user |
| POST | `/notification/execute` | Execute pending notifications (send via Discord/iMessage) |

### MCP (Model Context Protocol)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/mcp/` | JSON-RPC handler — internal clients (full tool access) |
| POST | `/mcp/copilot/` | JSON-RPC handler — GitHub Copilot (restricted) |
| POST | `/mcp/external/` | JSON-RPC handler — external clients (restricted) |
| GET | `/mcp/` | Server info |
| GET | `/mcp/tools` | Tool discovery (OpenAI format) |
| POST | `/mcp/execute` | Generic tool execution |
| POST | `/mcp/copilot/execute` | Copilot tool execution with access control |

### Other

| Method | Path | Description |
|--------|------|-------------|
| POST | `/embedding` | Generate text embeddings via ChromaDB |

## Multi-Turn Pipeline (`/api/multiturn`)

This is the main conversation flow. Here's what happens step by step:

### 1. Context Preparation
- Resolve user ID (falls back to `@ADMIN` contact)
- Get user alias from contacts service
- Load agent-managed prompts from brainlets database
- Fetch recent summaries from ledger

### 2. Tool Selection
- **Always-on tools** (`always=True`): Sent every request — `memory`, `manage_prompt`, `get_personality`
- **Routed tools** (`always=False`): A cheap LLM call (gpt-4.1-nano via `router` mode) decides which are relevant — `github_issue`, `stickynotes`
- Tool guidance strings injected into system prompt

### 3. Ledger Synchronization
- Last 4 messages synced to ledger (`POST /sync/user`)
- Full message buffer retrieved (`GET /sync/get?prefix_user_timestamps=true`)
- Tool calls, function calls, tool call IDs preserved

### 4. Pre-Brainlets
- Brainlets sorted topologically (Kahn's algorithm for `depends_on`)
- Filtered by current mode (only run if mode matches brainlet's `modes` list)
- Currently active: **memory_search** — extracts keywords via LLM, updates heatmap, injects contextual memories

### 5. Proxy Request + Tool Loop (max 10 iterations)
```
loop:
  POST to proxy /api/multiturn
  if response has tool_calls:
    for each tool_call:
      call_tool(name, params)  ← direct function call, no HTTP
      sync tool call + result to ledger
      append to messages
    continue loop
  else:
    sync assistant response to ledger
    break
```

### 6. Post-Brainlets
- Same sorting/filtering as pre-brainlets
- Run after LLM response (side effects, logging)
- Results NOT synced to ledger

## Tool System

Decorator-based, auto-discovering. No JSON files, no manual registration.

### How It Works

Tools live in `app/tools/*.py`. Each file has a `@tool`-decorated async function:

```python
@tool(
    name="my_tool",
    description="Does a thing",
    parameters={...},        # JSON Schema
    persistent=True,         # Log to ledger
    always=True,             # Always sent to LLM (vs routed)
    clients=["internal"],    # Access control for MCP endpoints
    guidance="Extra context for system prompt",
)
async def my_tool(parameters: dict) -> ToolResponse:
    return ToolResponse(result={"status": "ok"})
```

At import time, `__init__.py` scans all files in `app/tools/`, finds functions with `_tool_meta`, and registers them.

### Built-in Tools

| Tool | Always | Persistent | Clients | What It Does |
|------|--------|-----------|---------|-------------|
| `get_personality` | Yes | No | internal, copilot | Returns style guidelines |
| `manage_prompt` | Yes | Yes | internal | Add/delete/list agent prompts (SQLite) |
| `memory` | Yes | Yes | internal, external | Search/create/update/delete memories via ledger |
| `github_issue` | No | Yes | internal, copilot | GitHub issue management via API |
| `stickynotes` | No | Yes | internal | Persistent reminders via stickynotes service |

### Registry API (`app/tools/__init__.py`)

| Function | Purpose |
|----------|---------|
| `get_tool(name)` | Get callable or None |
| `get_openai_tools(client_type)` | All tools in OpenAI format, filtered by access |
| `get_mcp_tools(client_type)` | All tools in MCP format, filtered |
| `get_always_tools(client_type)` | Only `always=True` tools |
| `get_routed_tools_catalog()` | `{name: desc}` for router input |
| `call_tool(name, params)` | Execute locally, fallback to MCP client |
| `get_guidance_for_tools(names)` | Concatenated guidance strings |

### Adding a New Tool

1. Create `app/tools/my_tool.py` with `@tool` decorator
2. Save. Docker auto-restarts. Tool is live.

No JSON files. No executor mapping. No routes to register.

## Brainlet System

Modular pre/post processing pipeline. Brainlets are async functions configured in `config.json`:

```json
{
    "name": "memory_search",
    "description": "Injects contextual memories",
    "model": "default",
    "provider": "openai",
    "execution_stage": "pre",
    "depends_on": [],
    "options": { "max_completion_tokens": 64 },
    "modes": ["default", "work", "tts"]
}
```

- **Pre-execution**: Run before LLM call (context enrichment)
- **Post-execution**: Run after LLM response (side effects)
- **Dependency ordering**: Topological sort via `depends_on`
- **Mode filtering**: Only execute for matching modes

### Active Brainlets

**memory_search** (pre): Extracts keywords from conversation via singleturn LLM call → updates keyword heatmap in ledger → retrieves top contextual memories → injects as tool messages.

### Adding a New Brainlet

1. Create `app/brainlets/my_brainlet.py` with standard signature:
   ```python
   async def my_brainlet(brainlets_output: dict, request: MultiTurnRequest):
       # ... process ...
       return result  # dict or list, merged into messages
   ```
2. Import in `app/brainlets/__init__.py`
3. Add config entry to `config.json` brainlets array

## MCP Integration

Three JSON-RPC 2.0 endpoints with client-based access control:

- **`/mcp/`** — Internal (full access to all tools)
- **`/mcp/copilot/`** — GitHub Copilot (`github_issue`, `get_personality`)
- **`/mcp/external/`** — External clients (`memory`, and future tools)

Access control configured in `/app/config/mcp_clients.json` (host path `~/.kirishima/mcp_clients.json`). Tool-level errors are returned as successful MCP responses with `isError=True` (not JSON-RPC errors) to prevent McpError on client side.

## Notification System

- `POST /notification` creates a notification in SQLite
- `POST /notification/execute` checks user activity, routes notification to Discord DM or iMessage
- Prefers iMessage if contact has it, falls back to Discord
- Skips if user is currently active on web

## File Structure

```
app/
├── app.py                      # FastAPI setup, lifespan, router registration
├── config.py                   # Constants (summary periods, timeouts)
├── setup.py                    # DB init (status, notifications, last_seen, brainlets)
├── util.py                     # Cross-service HTTP helpers (contacts, ledger, summaries)
├── modes.py                    # Mode get/set (SQLite-backed)
├── last_seen.py                # User activity tracking
├── embedding.py                # ChromaDB embedding endpoint
├── message/
│   ├── multiturn.py            # PRIMARY ORCHESTRATOR — full pipeline
│   └── singleturn.py           # Simple proxy passthrough
├── tools/
│   ├── __init__.py             # Registry, discovery, dispatch API
│   ├── base.py                 # @tool decorator, ToolMeta, ToolResponse
│   ├── router.py               # Cheap LLM call to select relevant routed tools
│   ├── get_personality.py      # Style guidelines (always=True)
│   ├── manage_prompt.py        # Agent self-modification prompts (always=True)
│   ├── memory_management.py    # Ledger memory CRUD (always=True)
│   ├── github_issue.py         # GitHub issues (routed)
│   └── stickynotes.py          # Persistent reminders (routed)
├── brainlets/
│   ├── __init__.py             # Imports
│   └── memory_search.py        # Keyword extraction → heatmap → memory injection
├── routes/
│   └── mcp.py                  # MCP JSON-RPC handler (3 client endpoints)
├── services/
│   └── mcp_client/
│       └── client.py           # HTTP client for external MCP servers
├── notification/
│   ├── post.py                 # Create notifications
│   ├── get.py                  # Retrieve notifications
│   ├── delete.py               # Delete notifications (internal only)
│   ├── callback.py             # Execute pending notifications
│   └── util.py                 # Discord/iMessage send helpers
```

## Service Dependencies

| Service | How Brain Uses It |
|---------|-------------------|
| **Proxy** | All LLM requests (`/api/singleturn`, `/api/multiturn`) |
| **Ledger** | Message sync, memory search, heatmap updates, summaries |
| **Contacts** | Admin user resolution, user alias lookup |
| **Discord** | Notification delivery (`/dm`) |
| **iMessage** | Notification delivery (`/imessage/send`) |
| **Stickynotes** | CRUD for persistent reminders |
| **ChromaDB** | Text embeddings |

## Known Issues and Recommendations

### Issues

1. **Tool call array truncation** — `multiturn.py:165` takes only the first element if `tool_calls` is a list. Loses subsequent tool calls in multi-tool responses. Should preserve the full array.

2. **Hardcoded user ID in manage_prompt** — `manage_prompt.py:22` uses a stub UUID. All prompts are associated with one hardcoded user. Comment says "replace with actual user resolution when multi-user lands."

3. **Summaries raise HTTPException when empty** — `multiturn.py:107-113` raises 404 if no summaries exist. Summaries are optional context and should degrade gracefully.

4. **mcp_clients.json lists nonexistent tools** — References `email`, `calendar`, `contacts`, `lists`, `smarthome` tools that don't exist yet. These are placeholders for future development.

5. **Brainlet output merging is fragile** — `multiturn.py:248-255` handles nested dict/list structures by accident. Should standardize expected brainlet output format.

6. **Notification callback has duplicate code** — `callback.py` has ~45 lines of nearly identical logic for active vs inactive users. Should extract to helper.

7. **Bare exception catches** — Several places (e.g., `embedding.py:59`) catch all exceptions including SystemExit. Should use specific exception types.

8. **Provider resolution duplicated** — `multiturn.py:136-142` resolves provider from mode, but proxy already does this. Brain shouldn't need to know provider details.

9. **Personality version stale** — `get_personality.py:14` has `PERSONALITY_VERSION = "2025-08-14.1"`. Should be updated or auto-generated.

10. **notification_delete not exposed as endpoint** — Function exists but router never included in app. Can only be called internally from callback.

### Recommendations

- Fix tool_calls handling to preserve full array (OpenAI spec compliance)
- Make summaries optional — catch and log, don't raise
- Clean up mcp_clients.json to match actual tool inventory
- Standardize brainlet output format (always return list of messages)
- Extract notification send logic into shared helper to reduce duplication
- Add proper exception handling (no bare `except:`)
