# Kirishima Tool System Restructure — Reference Guide

This document explains what OpenClaw does with "skills," what Kirishima currently does with tools/MCP, where Kirishima's tool system is messy, and a step-by-step guide for restructuring it. Written for reference during implementation with any model.

---

## Part 1: What OpenClaw's "Skills" System Actually Is

OpenClaw's skills are **not code and not MCP**. They are Markdown files (`SKILL.md`) with YAML frontmatter that serve as documentation for the AI agent.

### How it works:
1. Each skill is a directory with a `SKILL.md` file (e.g., `skills/slack/SKILL.md`)
2. The YAML frontmatter declares metadata: name, description, required binaries, env vars, OS restrictions, emoji
3. At runtime, eligible skills are listed in the agent's system prompt as a brief index
4. When the agent decides it needs a skill, it reads the full `SKILL.md` file using a `read` tool
5. The Markdown content tells the agent HOW to use the associated tool (what actions are available, what parameters to pass, examples)
6. The agent then calls actual tools (bash, slack API, github CLI, etc.) based on what it learned from the skill doc

### Key architectural choices:
- **Skills are discovery/documentation, not execution.** The actual tool execution is separate.
- **MCP is handled independently** via a bridge tool called `mcporter` — explicitly decoupled from skills.
- **Auto-discovery** — skills are found by scanning directories, no manual registry.
- **Single source of truth** — everything about a skill lives in one file.

### What's relevant for Kirishima:
- **Single source of truth per tool** — Kirishima should stop scattering tool definitions across multiple JSON files.
- **Auto-discovery** — tools should register themselves by existing, not by being manually added to a config.
- **Metadata on the tool itself** — each tool should declare its own access rules, logging behavior, and dependencies.

### What's NOT relevant for Kirishima:
- **Markdown docs as prompt injection** — Kirishima uses OpenAI function calling. The LLM gets tool schemas directly; injecting separate Markdown would waste tokens.
- **Multi-source priority ordering** (bundled, managed, personal, workspace) — Kirishima is a single deployment, not a plugin ecosystem.
- **Decoupling skills from MCP** — In Kirishima, the tool definition IS the execution contract. Keeping them together is correct.

---

## Part 2: The Current State of Kirishima's Tool System

### Problem: Tool definitions exist in THREE different JSON files

**File 1: `services/brain/app/tools.json`** (legacy)
- OpenAI function calling format
- Contains 5 tools: `manage_prompt`, `memory`, `github_issue`, `smarthome`, `stickynotes`
- Some definitions are stale (e.g., memory still uses `add` action instead of `create`)

**File 2: `services/brain/app/config/tools.json`**
- MCP-native format with `inputSchema`
- Contains only 3 tools: `get_personality`, `github_issue`, `memory`
- This is what the MCP server routes in `routes/mcp.py` actually read

**File 3: `services/brain/app/config/mcp_tools.json`**
- Custom format with `parameters`, `returns`, `depends_on`, `persistent` fields
- Contains all 11 tools (the most complete file)
- This is what `registry.py` loads
- But it's NOT what the MCP server serves and NOT what gets sent to the LLM

### Problem: Tool implementations exist in TWO different directories

**Old: `services/brain/app/tools/`**
- 8 files with raw dict returns, no standard response model
- These are NOT used by the MCP path anymore but still exist in the codebase

**New: `services/brain/app/services/mcp/`**
- 10 tool implementation files: `memory.py`, `github_issue.py`, `manage_prompt.py`, `stickynotes.py`, `smarthome.py`, `calendar.py`, `contacts.py`, `email.py`, `lists.py`, `get_personality.py`
- Plus infrastructure: `executor.py`, `registry.py`, `dependencies.py`
- Each tool is an async function taking `Dict[str, Any]`, returning a response object
- Each makes HTTP calls to the relevant microservice

### Problem: Inconsistent response types

- `memory.py`, `github_issue.py`, `get_personality.py` return `ToolCallResponse` (fields: `result`, `error`)
- All other tools return `MCPToolResponse` (fields: `success`, `result`, `error`)
- `MCPToolResponse` may not even be properly defined in current `shared/models/mcp.py`

### Problem: Brain calls itself via HTTP to run its own tools

The tool dispatch flow in `multiturn.py` (lines ~284-336):
1. LLM returns `tool_calls` in its response
2. Brain creates `MCPClient` instances from config
3. For each client, it opens an HTTP connection, lists tools via JSON-RPC, checks if the tool name matches
4. If found, calls the tool via another HTTP request through the MCP protocol
5. This goes through `routes/mcp.py`, which does a dynamic import of the tool module

**This is a full network round-trip to call your own code.** Brain is connecting to itself as an MCP server.

### Problem: Hardcoded mappings alongside dynamic discovery

`executor.py` has a manual `module_mapping` dict:
```python
module_mapping = {
    "github_issue": "github_issue",
    "memory": "memory",
    "manage_prompt": "manage_prompt",
    # ...etc, manually maintained
}
```
This duplicates what dynamic discovery already provides and must be manually updated when adding tools.

### Problem: `registry.py` has redundant interfaces

Both a `ToolRegistry` class and standalone functions (`get_available_tools()`, `is_tool_available()`) that do the same thing.

### What IS working:
- The MCP server endpoints (`/mcp/`, `/mcp/copilot/`, `/mcp/external/`) with client-based access control
- The `MCPClient` for connecting to external MCP servers
- Individual tool implementations (they work, they're just inconsistent)
- Client access control via `mcp_clients.json`

---

## Part 3: Target Architecture

### Core idea: Each tool is a single, self-registering Python module

Replace all three JSON files and both implementation directories with one directory of decorator-based tool modules that auto-register at startup.

### Directory structure:
```
services/brain/app/tools/
    __init__.py          # Auto-discovery logic, registry, dispatch helpers
    base.py              # @tool decorator and ToolResponse model
    get_personality.py   # Phase 1 proof of concept
    github_issue.py      # Phase 2
    manage_prompt.py     # Phase 2 (rewrite from scratch)
    memory.py            # Phase 2 (rewrite, fix inconsistent returns)
    router.py            # Phase 3 (tool router — not a tool itself, excluded from auto-discovery)
    # stickynotes.py     # Deferred — add when needed
    # smarthome.py       # Deferred — add when Home Assistant is back
    # External MCP tools (email, calendar, contacts, lists) handled by MCPClient, no local files needed
```

### The `@tool` decorator

Each tool module has a single async function decorated with `@tool(...)`. The decorator carries ALL metadata — no separate JSON file needed.

```python
@tool(
    name="memory",
    description="Comprehensive memory management - search, create, update, delete, list memories",
    persistent=True,                    # logged to ledger
    always=True,                        # always included in LLM calls (not routed)
    clients=["internal", "external"],   # who can call this tool
    service="ledger",                   # which microservice it depends on (informational)
    parameters={                        # JSON Schema (OpenAI function calling format)
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search", "create", "update", "delete", "list", "get"],
                "description": "The action to perform"
            },
            # ...rest of schema
        },
        "required": ["action"]
    }
)
async def memory(parameters: dict) -> ToolResponse:
    action = parameters.get("action", "search")
    # ...implementation
    return ToolResponse(result={"status": "ok", "data": result})
```

What the decorator does internally: attaches metadata to the function as `fn._tool_meta`. That's it — it's just metadata tagging.

### The `ToolResponse` model

One model, used everywhere:
```python
class ToolResponse(BaseModel):
    result: Optional[Any] = None
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None
```

Replaces both `ToolCallResponse` and `MCPToolResponse`.

### The auto-discovery registry (`__init__.py`)

On import, scans all `.py` files in the `tools/` directory, imports each, finds functions with `_tool_meta`, and builds a registry dict.

Provides these functions:
- **`get_tool(name)`** — returns the callable function
- **`get_openai_tools(client_type="internal")`** — returns tools in OpenAI function calling format, filtered by client access
- **`get_mcp_tools(client_type="internal")`** — returns tools in MCP format, filtered
- **`get_always_tools(client_type="internal")`** — returns only `always=True` tools in OpenAI format
- **`get_routed_tools_catalog()`** — returns `always=False` tools as a lightweight catalog (name + description only) for the tool router
- **`call_tool(name, params)`** — executes tool, returns ToolResponse. Falls through to MCPClient for external MCP servers if tool isn't local.

### Simplified dispatch in `multiturn.py`

**Before (current):**
```python
mcp_clients = MCPClient.from_config()
tool_result = None
for mcp_client in mcp_clients:
    tools = await mcp_client.list_tools()
    if any(t.get('name') == fn for t in tools):
        tool_result = await mcp_client.call_tool(fn, args_dict)
        break
```

**After:**
```python
from app.tools import call_tool
result = await call_tool(fn, args_dict)
tool_result = result.model_dump()
```

No HTTP round-trip. No MCP client. Direct function call.

### External MCP servers still supported

`call_tool()` checks local registry first. If the tool isn't found locally, it falls through to MCPClient for external MCP servers configured in `config.json`. Local and external tools are transparent to the caller.

### Tool router (selective tool presentation)

**Problem:** Passing all tools to the LLM on every call wastes tokens and can confuse smaller models. Some tools (like `calendar`) are only relevant occasionally. Every tool schema in the request is tokens you're paying for.

**Solution:** A cheap, fast LLM call classifies the user's input and selects which tools to include.

**Two tiers — no weights, no complexity:**

- **Always-on tools** (`always=True`): Included in every LLM call regardless. These are tools the conversational model should always have access to — `memory` (the model can't reliably decide when to store memories on its own), `manage_prompt`, `get_personality`. Skip the router entirely for these.
- **Routed tools** (`always=False`): Only included when the router says they're relevant — `calendar`, `contacts`, `email`, `lists`, `stickynotes`, `smarthome`, `github_issue`. External MCP tools default to `always=False`.

**How the router works:**

The router gets:
- The user's message (and optionally the last 2-3 messages for context)
- A lightweight tool catalog: just names and one-line descriptions of all `always=False` tools (both local and external MCP)

The router returns:
- A list of tool names to include

That's it. Small prompt (~500 tokens in), small response (~50 tokens out). Run it on Haiku, gpt-4.1-mini, or a local model via Ollama. Cost per call is negligible.

**Router prompt structure:**
```
You are a tool router. Given a user message, decide which tools (if any) are relevant.

Available tools:
- calendar: Manage Google Calendar events (list, create, update, delete)
- contacts: Look up and manage contacts
- email: Send, read, and search emails
- lists: Manage task lists
- stickynotes: Persistent reminders and task tracking
- smarthome: Control smart home devices and lighting
- github_issue: Create, view, and manage GitHub issues

User message: "{user_message}"

Return a JSON array of tool names that are relevant, or an empty array if none apply.
When in doubt, include the tool.
```

**Where it fits in the flow:**

Current flow:
1. Get user message
2. Run pre-execution brainlets
3. Gather ALL tools
4. Send to proxy/LLM

New flow:
1. Get user message
2. Run pre-execution brainlets
3. Get always-on tools from registry (`get_always_tools()`)
4. **Call tool router via proxy (cheap model) with routed tool catalog → get relevant tool names**
5. Get full schemas for router-selected tools from registry
6. Merge always-on + router-selected tools
7. Send to proxy/LLM with only the relevant tools

**Implementation:** One new async function in brain, something like `app/tools/router.py`. It calls proxy with a singleturn request using a cheap model mode (e.g., `router` mode mapped to Haiku/mini in proxy config). The function takes the user message and returns a list of tool name strings.

**Catalog generation:** The catalog is built automatically from the registry. `get_routed_tools_catalog()` returns all `always=False` tools (both local and external MCP) as `{name: description}` pairs. When external MCP servers are discovered, their tools are added to this catalog with `always=False` by default.

**Tuning:** If the router isn't selecting a tool when it should, improve that tool's `description` in the decorator. The description is what the router sees. Clear, specific descriptions > numerical weights.

**Cost math:** Say you have 15 tools with full schemas at ~250 tokens each = ~3,750 tokens per request just in tool definitions. With the router, always-on tools might be 3 tools (~750 tokens) plus 2-3 router-selected tools (~500-750 tokens). The router call itself costs ~600 tokens on a cheap model. Net savings: ~2,000+ tokens per message on the expensive conversational model. Over 100 messages/day, that's 200K tokens saved — meaningful at $20-30/month.

### Optional: guidance field for complex tools

For tools where the LLM needs more context than just the parameter schema (like `memory` with 6 different actions), add an optional `guidance` string to the decorator:

```python
@tool(
    name="memory",
    description="Comprehensive memory management",
    guidance="Always search before creating to avoid duplicates. Use specific keywords.",
    # ...
)
```

This string can be injected into the system prompt when the tool is available. Lightweight equivalent of OpenClaw's SKILL.md content. Most tools won't need it.

---

## Part 4: What Gets Deleted vs Kept

### Delete:
| File/Directory | Why |
|---|---|
| `brain/app/tools.json` | Legacy, stale, replaced by decorators |
| `brain/app/config/tools.json` | MCP-format subset, replaced by decorators |
| `brain/app/config/mcp_tools.json` | Custom format, replaced by decorators |
| `brain/app/services/mcp/executor.py` | Hardcoded mapping, replaced by auto-discovery |
| `brain/app/services/mcp/registry.py` | Redundant, replaced by `tools/__init__.py` |
| `brain/app/services/mcp/dependencies.py` | `depends_on` is empty for every tool; add back when needed |
| `brain/app/services/mcp/*.py` (tool files) | Migrated to `brain/app/tools/` |
| `brain/app/tools/` (old implementations) | Replaced by new decorator-based versions in same path |

### Keep:
| File/Directory | Why |
|---|---|
| `brain/app/config/mcp_clients.json` | Admin-level client access control (read by new registry) |
| `brain/app/services/mcp_client/client.py` | MCPClient for external MCP servers |
| `brain/app/services/mcp_client/util.py` | Format conversion utilities |
| `brain/app/routes/mcp.py` | MCP server endpoints (simplified to use new registry) |

---

## Part 5: Step-by-Step Implementation Guide

### Phase 1: Build the foundation (no existing code changes)

**Goal:** Create the new tool infrastructure alongside the old. Nothing breaks.

**Step 1.1: Create `services/brain/app/tools/base.py`**
- Define the `@tool` decorator that attaches metadata to functions
- Define the `ToolResponse` model (Pydantic BaseModel)
- The decorator should accept: `name`, `description`, `parameters` (JSON Schema), `persistent` (bool), `always` (bool — always present to LLM, or routed), `clients` (list of strings), `service` (optional string), `guidance` (optional string)

**Step 1.2: Create `services/brain/app/tools/__init__.py`**
- On module import, scan all `.py` files in the directory (excluding `__init__.py` and `base.py`)
- Import each module, find functions with `_tool_meta` attribute
- Build internal registry dict: `{name: {"function": fn, "meta": fn._tool_meta}}`
- Implement `get_openai_tools(client_type)` — transforms metadata into OpenAI function calling format, filters by `clients` list
- Implement `get_mcp_tools(client_type)` — transforms metadata into MCP tool format, filters by `clients` list
- Implement `call_tool(name, params)` — looks up function in registry, calls it, returns ToolResponse. If not found locally, try external MCP clients from config.
- Read `mcp_clients.json` for admin-level access overrides

**Step 1.3: Migrate `get_personality` as proof of concept**
- Create `services/brain/app/tools/get_personality.py` with `@tool` decorator
- This is the simplest tool (no HTTP calls, just reads config)
- Pull metadata from current `mcp_tools.json` entry
- Verify it appears in the auto-discovery registry
- Test: import `app.tools` and call `get_openai_tools()` — confirm `get_personality` shows up

**Complete example — what `get_personality.py` should look like after migration:**

```python
"""get_personality tool — returns style/personality guidelines for target LLM models."""

from datetime import datetime, timezone
from app.tools.base import tool, ToolResponse
from shared.log_config import get_logger

logger = get_logger(f"brain.{__name__}")

PERSONALITY_VERSION = "2025-08-14.1"

STYLE_SECTIONS = {
    "gpt-5": "Tone: incisive, concise, a touch of dry wit. Avoid fluff. Provide direct answer first, context second. Challenge assumptions politely. No performative apologies.\nFormatting: short paragraphs or tight bullets. Keep code minimal and focused. Prefer specifics over abstractions.\nFailure Mode Handling: state the blocker succinctly and offer the next best actionable step.",
    "gpt-4.1": "Tone: pragmatic senior engineer. Mild sarcasm allowed. Skip corporate cheer. Always surface the TL;DR in first sentence.\nFormatting: bullets for lists, headings only when adding structure. Avoid long monolithic paragraphs.\nError Handling: summarize error, list 1-2 likely root causes, propose fix steps.",
    "claude-sonnet-4": "Tone: thoughtful but trim. Maintain clarity, no rambling. Provide rationale only if it materially aids a decision.\nFormatting: lean bullet lists; inline code for identifiers; fenced blocks only for multi-line snippets.\nGuardrails: never invent unverifiable facts; explicitly label assumptions.",
    "default": "Tone: concise, direct, lightly dry humor. No filler openings ('Certainly', etc.).\nFormatting: optimize for scan-ability; answers lead with conclusion.",
}

APPLICATION_INSTRUCTIONS = (
    "Select the style section matching the active model name. If multiple keys could match, "
    "choose the most specific. If a requested model isn't present, fall back to 'default'. "
    "Always retrieve this tool before other tool usage in a new session."
)


@tool(
    name="get_personality",
    description="Return current multi-model personality/style guidelines for conversational tone; Copilot must call this before other tools.",
    persistent=False,
    always=True,
    clients=["internal", "copilot"],
    parameters={
        "type": "object",
        "properties": {},
        "required": []
    }
)
async def get_personality(parameters: dict) -> ToolResponse:
    """Return full personality/style guidance."""
    payload = {
        "version": PERSONALITY_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "style_sections": STYLE_SECTIONS,
        "instructions": APPLICATION_INSTRUCTIONS,
    }
    logger.info(f"Served personality version {PERSONALITY_VERSION}")
    return ToolResponse(result=payload)
```

**This is the pattern every other tool should follow.** The only differences per tool are:
- The `@tool(...)` metadata (name, description, parameters schema, persistent, always, clients)
- The function body (HTTP calls to services, local logic, etc.)
- The return value (always `ToolResponse(result=...)` on success, `ToolResponse(error=...)` on failure)

### Phase 2: Migrate core tools only

**Goal:** Migrate only the 4 essential tools to the new decorator pattern. Everything else is deferred or replaced.

**What happened to the other tools:**
- **`email`, `calendar`, `contacts`, `lists`** — will be replaced by an external Google MCP server. Don't migrate; delete the old implementations.
- **`stickynotes`** — custom implementation (not a Google API wrapper). Keep the stickynotes microservice, but defer migrating the tool. Add it later when needed — it's just one file following the pattern.
- **`smarthome`** — Home Assistant is not currently running. Keep the smarthome microservice, defer the tool. Migrate when HA is back online.

**Current state of the 4 tools being migrated:**
- `get_personality` — working, clean, already uses `ToolCallResponse` correctly
- `github_issue` — working, fixed in commit `cce2162`, uses `ToolCallResponse(result={"success": True/False, ...})` pattern. Note: uses sync `requests` library instead of async `httpx` — fix during migration.
- `memory` — partially fixed in `cce2162`, **inconsistent return patterns** (some functions wrap in `{"success": True, "data": ...}`, others don't). Rewrite during migration to be consistent.
- `manage_prompt` — **never touched** in the MCP rework, still imports `MCPToolResponse` which no longer exists in `shared/models/mcp.py`. Currently broken for MCP calls. Rewrite from scratch during migration.

For each tool:
1. Create new file in `services/brain/app/tools/`
2. Use the existing implementation as reference but write clean code with `ToolResponse`
3. Add `@tool` decorator with metadata from `mcp_tools.json`
4. Return `ToolResponse(result=...)` on success, `ToolResponse(error=...)` on failure
5. Use `httpx` (async) for all HTTP calls, not `requests` (sync)

**Migration order:**
1. `get_personality` — done in Phase 1 (proof of concept)
2. `github_issue` — already working, straightforward copy + cleanup
3. `manage_prompt` — rewrite from scratch (old version is broken)
4. `memory` — rewrite, standardize the inconsistent return patterns

**Per-tool checklist:**
- [ ] File created in `app/tools/`
- [ ] `@tool` decorator has correct name, description, parameters schema
- [ ] `persistent` flag set correctly
- [ ] `always` flag set correctly (see Part 7 table)
- [ ] `clients` list set correctly (check `mcp_clients.json` for current access)
- [ ] Returns `ToolResponse` consistently (never use the `error` field on `ToolCallResponse` — embed errors in `result`)
- [ ] Uses `httpx.AsyncClient` for HTTP calls (not sync `requests`)
- [ ] Uses shared logger: `logger = get_logger(f"brain.{__name__}")`

### Phase 3: Rewire dispatch and add tool router

**Goal:** Make brain use the new registry instead of the old paths, and add the tool router.

**Step 3.1: Update `services/brain/app/message/multiturn.py`**
- Find the tool call loop (around lines 284-336)
- Replace `MCPClient.from_config()` / `list_tools()` / `call_tool()` chain with:
  ```python
  from app.tools import call_tool
  result = await call_tool(fn, args_dict)
  ```
- Keep ledger sync logic (the part that POSTs to `/sync/tool`)
- Keep the message appending logic

**Step 3.1b: Add tool router to request setup in `multiturn.py`**
- Before the proxy call, replace "gather all tools" with:
  ```python
  from app.tools import get_always_tools, get_routed_tools_catalog
  from app.tools.router import route_tools

  always_tools = get_always_tools(client_type="internal")
  routed_catalog = get_routed_tools_catalog()
  selected_names = await route_tools(user_message, routed_catalog)
  selected_tools = get_openai_tools_by_names(selected_names, client_type="internal")
  tools = always_tools + selected_tools
  ```
- The proxy call then gets only the relevant tools instead of everything

**Step 3.1c: Create `services/brain/app/tools/router.py`**
- Single async function: `route_tools(message: str, catalog: dict) -> list[str]`
- Calls proxy with a singleturn request using a cheap model mode (e.g., `router`)
- Prompt: list of tool names + descriptions, user message, return JSON array of relevant names
- Add `router` mode to proxy config (mapped to Haiku, gpt-4.1-mini, or local Ollama model)
- Handle failures gracefully: if the router call fails, fall back to including all routed tools

**Step 3.2: Update `services/brain/app/routes/mcp.py`**
- Replace `get_all_tools()` calls with `from app.tools import get_mcp_tools`
- Replace dynamic import tool execution with `from app.tools import call_tool`
- Keep the client-type-based URL routing (`/mcp/`, `/mcp/copilot/`, `/mcp/external/`)

**Step 3.3: Update tool format conversion**
- Check `services/brain/app/services/mcp_client/util.py` — if it has `mcp_tools_to_openai()` conversion, it may no longer be needed (the registry provides both formats natively)

### Phase 4: Delete the old stuff

**Goal:** Remove all the dead code and duplicate configs.

**Delete — tool definitions (all 3 JSON files):**
- `services/brain/app/tools.json`
- `services/brain/app/config/tools.json`
- `services/brain/app/config/mcp_tools.json`

**Delete — old infrastructure:**
- `services/brain/app/services/mcp/executor.py`
- `services/brain/app/services/mcp/registry.py`
- `services/brain/app/services/mcp/dependencies.py`

**Delete — all tool implementations from `services/brain/app/services/mcp/`:**
- `memory.py`, `github_issue.py`, `manage_prompt.py`, `get_personality.py` (migrated to `app/tools/`)
- `email.py`, `calendar.py`, `contacts.py`, `lists.py` (replaced by external Google MCP server)
- `stickynotes.py`, `smarthome.py` (deferred — will be rewritten from scratch when needed)
- Delete the entire `services/brain/app/services/mcp/` directory if nothing else imports from it

**Delete — old tool implementations directory:**
- `services/brain/app/tools/` old files (8 files with raw dict returns, pre-MCP era). These are replaced by the new decorator-based files in the same path.

**Keep:**
- `services/brain/app/config/mcp_clients.json` — client access control
- `services/brain/app/services/mcp_client/` — MCPClient for external MCP servers
- `services/brain/app/routes/mcp.py` — MCP server endpoints (simplified to use new registry)
- `services/stickynotes/` — the microservice itself stays, just no brain-side tool wrapper for now
- `services/smarthome/` — the microservice itself stays, tool wrapper deferred

**Update docs:**
- `docs/MCP_Planning.md` — reflect new architecture
- `services/brain/README.md` — if it references old tool paths

---

## Part 6: Adding a New Tool After Restructure

This is the whole point. After the restructure, adding a new tool is:

1. Create one file: `services/brain/app/tools/my_new_tool.py`
2. Write the function with `@tool` decorator
3. Save. Docker auto-restarts. Tool is live.

No JSON files to edit. No executor mapping to update. No routes to register. No registry to maintain. Auto-discovery handles everything.

Claude (Sonnet or otherwise) can do this in one shot — it just needs to follow the pattern of any existing tool file in the directory.

---

## Part 7: Reference — Tool Inventory

### Migrating now (Phase 2):

| Tool | Service Called | Actions | Persistent | Always | Clients | Status |
|------|---------------|---------|------------|--------|---------|--------|
| `get_personality` | Local config | (returns data) | No | **Yes** | internal, copilot | Working, clean |
| `github_issue` | GitHub API | create, view, comment, close, list, list_comments | Yes | No | internal, copilot | Working, needs async fix |
| `manage_prompt` | Local SQLite | add, delete, list | Yes | **Yes** | internal only | **Broken** — imports deleted model |
| `memory` | ledger | search, create, update, delete, list, get | Yes | **Yes** | internal, external | Inconsistent returns |

### Replaced by external Google MCP server (delete, don't migrate):

| Tool | Replacement |
|------|-------------|
| `email` | External Google MCP server |
| `calendar` | External Google MCP server |
| `contacts` | External Google MCP server |
| `lists` | External Google MCP server |

### Deferred (keep microservice, migrate tool later):

| Tool | Service Called | Why deferred |
|------|---------------|--------------|
| `stickynotes` | stickynotes service | Custom implementation, not urgent. Migrate when needed — one file. |
| `smarthome` | smarthome service | Home Assistant not currently running. Migrate when HA is back. |

### Always=Yes rationale:
- `memory`: The conversational LLM can't reliably decide when to store memories without seeing the tool. Always available.
- `manage_prompt`: Self-modification capability should always be accessible to the agent.
- `get_personality`: Lightweight (small schema), used for context. Always available.

### Tool router note:
With only 4 tools migrated initially (3 always-on + 1 routed), the tool router (Phase 3) isn't urgent. It becomes valuable when external MCP server tools are added and the total tool count grows again. Implement the router infrastructure now, but it's fine if the catalog is small at first.
