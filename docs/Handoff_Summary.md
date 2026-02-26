# Kirishima Development Handoff Summary

This document captures all analysis, decisions, and plans from the initial Claude Code session (2026-02-24). Use this as context when continuing work in GitHub Copilot or any other environment.

---

## 1. What Was Done This Session

- **Created `CLAUDE.md`** in repo root — project context file for Claude Code sessions
- **Created memory files** at `~/.claude/projects/-home-randi-kirishima/memory/` — persistent context across Claude Code sessions
- **Created `docs/Tool_System_Restructure.md`** — comprehensive plan for restructuring the tool/MCP system (detailed implementation guide with phases)
- **Analyzed OpenClaw's skills system** — determined it's documentation-driven (Markdown files), not MCP-based, and mostly not relevant to Kirishima's architecture
- **Performed full architectural review** of brain, proxy, and ledger services

---

## 2. Tool System Restructure (Primary Plan)

**Full plan lives in:** `docs/Tool_System_Restructure.md`

**Summary:** Replace the scattered tool system (3 JSON definition files, 2 implementation directories, self-HTTP-round-trip dispatch, inconsistent response types) with a decorator-based, auto-discovering tool registry.

**Key decisions:**
- Each tool is one Python file with a `@tool` decorator carrying all metadata
- Auto-discovery at startup, no manual registry maintenance
- Direct function calls for local tools (eliminate the MCPClient self-round-trip)
- MCPClient kept for external MCP servers only
- Brain hosts the MCP server (no separate MCP microservice needed)
- Single `ToolResponse` model replaces `ToolCallResponse` and `MCPToolResponse`

**Tool router (sub-agent for tool selection):**
- Cheap/fast LLM call classifies user input and selects which tools to include
- Two tiers: `always=True` (always included: memory, manage_prompt, get_personality) and `always=False` (routed: calendar, email, contacts, etc.)
- No weights, no complexity — just name + description catalog sent to cheap model
- Router returns list of tool names, brain merges with always-on tools
- Fallback: if router fails, include all tools
- New `router` mode in proxy config mapped to Haiku/mini/local model

**Phases:**
1. Build foundation (base.py, __init__.py, migrate get_personality)
2. Migrate all tools to decorator pattern
3. Rewire dispatch + add tool router
4. Delete old files

---

## 3. Architectural Issues Identified

### High Priority (fix during/alongside tool restructure):

**Config loaded from disk on every request**
- Every service re-reads `config.json` via `open()` + `json.load()` multiple times per request
- Fix: Load once at startup, hold in memory. Add reload endpoint if hot-reload needed.
- Affects: every service

**Tool execution loop has no max iteration guard**
- `multiturn.py` has `while True` with break only on non-tool-call response
- If LLM keeps requesting tools, this loops forever and burns API budget
- Fix: Add hard cap (10 iterations), log warning when hit
- Affects: `services/brain/app/message/multiturn.py`

**Dual prompt system in proxy**
- Centralized loader (JSON + Jinja) AND legacy Python module system with fallback
- Creates debugging ambiguity — which system is actually being used?
- Fix: Kill legacy Python modules, use centralized loader only
- Affects: `services/proxy/app/prompts/`

### Medium Priority (separate efforts):

**No graceful degradation for non-critical services**
- Every inter-service HTTP failure throws 500
- Fix: Wrap non-critical calls (contacts, stickynotes) in try/except that logs and continues
- Critical services (proxy, ledger) can still hard-fail

**Brainlet discovery is fragile**
- Uses `getattr()` which silently returns None if brainlet doesn't exist
- Fix: Apply same decorator/auto-discovery pattern as the tool restructure

**No database migration system**
- Tables created with `IF NOT EXISTS`, no way to alter schema without data loss
- Fix: Simple numbered SQL migration files + schema_version table (~30 lines of code)

### Ledger-Specific Issues:

**Three separate sync implementations**
- `routes/user.py`, `services/sync/user.py`, and `services/user/sync.py` — all doing variations of the same thing
- Fix: Consolidate to one function, one file, wrap in transaction

**Heatmap recalculates all memory scores on every update**
- Full table scan joining memories × tags × heatmap_score
- Fix: Incremental updates — only rescore memories with tags matching changed keywords

**LLM calls inside the data layer**
- Scan, dedup, and summary endpoints call LLMs directly, bypassing proxy
- Violates the "proxy is the only service that talks to LLMs" rule
- Fix: Move LLM-dependent operations to brain (or have them go through proxy). Ledger stays as pure storage + retrieval.

**Unused endpoints**
- Some endpoints are dead code. Worth identifying and removing during service audit.

### Things That Are Fine (don't fix):

- SQLite everywhere — correct for single-user personal assistant
- Microservice boundaries — well-drawn, appropriate count
- Docker-compose giving all env vars to all services — pragmatic, not worth optimizing
- Prompt complexity — inherently complex problem, Jinja approach is correct
- Ledger being one service (was previously split) — consolidation was right, they share a database

---

## 4. CLI Client Plan

**Purpose:** Debug/admin tool + chat interface for Kirishima, running locally (not a microservice).

**Architecture — two completely separate paths in one shell:**
```
kirishima-cli (local Python script on host)
    │
    ├── Chat (no slash prefix)
    │     → POST to API service or proxy /api/multiturn
    │     → CLI maintains its own local message array (list of message dicts)
    │     → appends user/assistant messages as conversation progresses
    │     → slash commands NEVER enter this array or touch ledger
    │     → standard OpenAI-compatible chat client behavior
    │
    └── Slash commands (/heatmap, /mode, /tools, etc.)
          → POST to brain /admin/command endpoint
          → brain routes internally to the right service
          → result returned and displayed
          → nothing enters conversation history, nothing touches ledger
          → completely invisible to the chat path
```

**Brain admin endpoint (new):** `POST /admin/command`
- Takes `{ "command": "heatmap", "args": {} }`
- Brain routes internally to the appropriate service (ledger, proxy, itself, etc.)
- Returns result to CLI
- Does NOT create chat completions, does NOT sync to ledger
- Completely separate from multiturn/singleturn paths
- Command routing logic lives in brain, not the CLI — CLI just sends command strings

**Location in repo:** `cli/` directory (NOT in `services/` — it's a client, not a service)
```
cli/
    __init__.py
    main.py          # Entry point, REPL loop
    client.py        # HTTP client wrapper (knows brain + API/proxy ports from config)
    commands.py      # Slash command definitions (name, help text, args parsing)
    display.py       # Output formatting (swap for textual TUI later)
    config.py        # Reads ~/.kirishima/config.json and .env for ports
```

**Brain-side:** `services/brain/app/routes/admin.py`
```
Command registry — each command is a handler function that knows which
service to call. Could use a decorator pattern like the tool system.
```

**Commands:**

Conversation/Context debugging:
- `/context` — show current message buffer for user
- `/tokens` — token count of current context window
- `/history [n]` — last N messages
- `/clear` — clear conversation buffer

Memory/Heatmap debugging:
- `/heatmap` — current keyword scores
- `/memories [query]` — search memories
- `/memory [id]` — get specific memory details
- `/topics` — list recent topics

System state:
- `/mode` — show current mode
- `/mode [name]` — switch mode
- `/tools` — list available tools (local + external MCP)
- `/services` — health check all services
- `/config [key]` — show config values

Brainlet/Prompt debugging:
- `/prompt` — current agent-managed prompt entries
- `/brainlets` — loaded brainlets and status

**Implementation phases:**
1. Brain admin endpoint + basic CLI REPL with slash commands (~200 lines CLI, ~150 lines brain endpoint)
2. Pretty TUI with `textual` (IRC-style split pane — scrolling output + input at bottom)
3. Mobile: point any OpenAI-compatible mobile app at the existing API service for chat (no slash commands on mobile)

---

## 5. Recommended Work Order

1. **Tool restructure** (Phases 1-4 from `docs/Tool_System_Restructure.md`)
2. **Config caching** (easy win, do alongside tool restructure)
3. **Tool loop max iterations** (5-minute fix)
4. **Tool router** (Phase 3 addition from restructure doc)
5. **Kill legacy prompt modules in proxy**
6. **CLI client** (Phase 1 — basic REPL)
7. **Service-by-service audit** (doc accuracy, dead endpoints, sync consolidation)
8. **Ledger fixes** (sync consolidation, incremental heatmap, move LLM calls out)
9. **Graceful degradation for non-critical services**
10. **Database migration system**

Items 1-3 are the foundation. Item 4 builds on 1. Items 5-10 are independent and can be done in any order.

---

## 6. Key File Locations

**Planning docs:**
- `docs/Tool_System_Restructure.md` — full tool restructure plan with implementation guide
- `docs/Full Architecture.md` — architectural principles and service overview
- `docs/MCP_Planning.md` — original MCP roadmap (partially superseded by restructure plan)
- `.github/copilot-instructions.md` — detailed technical reference (ledger schema, provider system)

**Brain service (primary target for restructure):**
- `services/brain/app/message/multiturn.py` — core orchestration, tool dispatch loop
- `services/brain/app/services/mcp/` — current tool implementations (to be migrated)
- `services/brain/app/tools/` — old tool implementations (to be replaced)
- `services/brain/app/routes/mcp.py` — MCP server endpoints
- `services/brain/app/services/mcp_client/client.py` — MCP client for external servers
- `services/brain/app/config/mcp_tools.json` — most complete tool definitions (metadata source for migration)
- `services/brain/app/config/mcp_clients.json` — client access control (keep)
- `services/brain/app/brainlets/` — brainlet implementations

**Proxy service:**
- `services/proxy/app/prompts/dispatcher.py` — dual prompt system (centralized + legacy fallback)
- `services/proxy/app/prompts/` — legacy Python prompt modules (candidates for deletion)
- `~/.kirishima/prompts/proxy/` — centralized prompt configs (JSON) and templates (Jinja)
- `services/proxy/app/util.py` — mode/model/provider resolution

**Ledger service:**
- `services/ledger/app/services/sync/` — sync implementations (3 versions, needs consolidation)
- `services/ledger/app/services/context/heatmap.py` — heatmap scoring (needs incremental update)
- `services/ledger/app/services/memory/scan.py` — memory extraction via LLM (should move to brain)

**Config:**
- `~/.kirishima/config.json` — main config (mounted as `/app/config/config.json` in Docker)
- `.env` — port definitions referenced by docker-compose
- `~/.kirishima/prompts/` — prompt templates and context files
