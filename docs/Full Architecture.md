# 🧠 Full Architecture

## 🧭 Architectural Principles

- **Brain is the primary orchestrator.** All message routing, tool execution, and service coordination flows through brain.
- **Proxy is the sole LLM gateway.** Prompt construction, model/provider resolution, and dispatch are all proxy's responsibility. No other service talks to LLMs directly.
- **HTTP-only inter-service communication.** No direct DB access across services. No shared state except via API calls.
- **All persistence uses SQLite** (WAL mode, foreign keys enabled).
- **Centralized logging via Graylog** (GELF + graypy). All services use `shared.log_config.get_logger()`.
- **Cross-platform conversation continuity.** Discord, iMessage, API, Gmail all feed one conversation thread via ledger.
- **Docker auto-restarts on code changes.** Never restart containers manually.

## 🌟 Core Innovations

### 🔥 Heatmap Memory System

The ledger implements a keyword-weighted memory retrieval system that tracks conversation context dynamically:

- **Weighted keywords**: Keywords classified as high (1.0), medium (0.7), or low (0.5) based on conversation relevance
- **Reinforcement**: Repeated keywords get 10% score boosts
- **Decay**: Unused keywords lose 0.08 per update cycle; below 0.1 they're removed
- **Memory scoring**: Each memory scored by sum of matching keyword scores, rescored on every heatmap update
- **No vector DB**: Pure SQLite with keyword-based scoring — simple, fast, effective

### 🧠 Self-Modifying Agency

The AI can modify its own system prompt through the `manage_prompt` tool:

- Prompts stored in SQLite (brainlets DB), injected into system prompt on every request
- Personality and behavioral changes persist across restarts
- Autonomous decisions about tone, style, and behavioral patterns

### 🔄 Unified Conversation Flow

All platform interactions feed into one conversation thread:

- Ledger normalizes messages from Discord, iMessage, Gmail, API into unified format
- Intelligent deduplication handles cross-posted or repeated messages
- Switch platforms mid-conversation without losing context

## 🧩 Services

### 🌐 API

OpenAI-compatible REST interface. Translates standard `/v1/completions` and `/v1/chat/completions` calls into internal requests to brain.

- Accepts "mode" names (not model names) — brain/proxy resolve to actual provider/model
- Special case: messages starting with `### Task` reroute to single-turn pipeline
- No memory, context, or summarization logic — pure passthrough

### 🧠 Brain

Central orchestrator. Coordinates all other services, manages the multi-turn conversation pipeline.

**Multi-turn pipeline** (`/api/multiturn`):
1. **Context prep**: Resolve user via contacts, load agent prompts, fetch summaries
2. **Tool selection**: Always-on tools (memory, manage_prompt, get_personality) + router-selected tools (github_issue, stickynotes) via cheap LLM call
3. **Ledger sync**: Last 4 messages synced, full buffer retrieved
4. **Pre-brainlets**: Topologically sorted, mode-filtered (currently: memory_search — extracts keywords, updates heatmap, injects contextual memories)
5. **Proxy + tool loop**: Send to proxy, if tool_calls returned → execute directly via `call_tool()` → sync to ledger → repeat (max 10 iterations)
6. **Post-brainlets**: Side effects, logging (not synced to ledger)

**Tool system**: Decorator-based, auto-discovering. `@tool` decorator in `app/tools/*.py` — no JSON files, no manual registration. Tools have access control for MCP endpoints (internal/copilot/external).

**MCP server**: Three JSON-RPC 2.0 endpoints with client-based access control:
- `/mcp/` — internal (full access)
- `/mcp/copilot/` — GitHub Copilot (restricted)
- `/mcp/external/` — external clients (restricted)

**Notifications**: Creates notifications in SQLite, executes via Discord DM or iMessage based on user activity status.

### 📇 Contacts

CRUD service for contact management. Cross-platform identity resolution — maps Discord IDs, iMessage addresses, email addresses to unified contact UUIDs.

- `@ADMIN` alias is critical — brain uses it to resolve the admin user
- Search by alias or field key/value (case-insensitive)
- Used by brain, iMessage, and Discord for sender resolution

### 💬 Discord

Discord DM bridge. Runs Discord.py bot + FastAPI server.

- **Incoming**: on_message → contact lookup → brain `/api/multiturn` → reply via DM
- **Outbound**: `POST /dm` for notification delivery
- DM-only, no server support

### 📺 Divoom

Controls Divoom Max Bluetooth display. Runs on host (not containerized) due to Bluetooth stack limitations.

- Displays emoji based on conversation tone, topic changes, TTS activity
- Exposes `/send` endpoint accepting emoji input
- Uses pixoo library, Twemoji-format images stored locally

### 📧 GoogleAPI

Gmail integration with OAuth2. Also contains a **Google Tasks implementation** (`/tasks/*`) that was built to replace the stickynotes service but the migration was never completed.

- Gmail: Send/receive email as part of conversation flow
- Tasks: Complete Google Tasks API integration with stickynotes-compatible endpoints, RRULE recurrence, due task monitoring — but brain still uses the standalone stickynotes service

### 💬 iMessage

BlueBubbles-powered iMessage bridge. BlueBubbles runs on a macOS machine.

- **Incoming**: BlueBubbles webhook → contact lookup → brain `/api/multiturn` → reply via BlueBubbles API
- **Outbound**: `POST /imessage/send` for notification delivery
- Auto-creates chats when sending to new recipients

### 🪪 Ledger

Persistent data store for all conversational data. The most data-rich service.

**Core systems**:
- **Message buffers**: Cross-platform message storage with sync, dedup, in-place editing
- **Memory system**: Long-term knowledge with keywords, categories, topics. Auto-extraction via LLM scanning.
- **Context heatmap**: Dynamic keyword relevance tracking for conversation-aware memory retrieval
- **Topics**: Conversation threading and categorization
- **Summaries**: Temporal summaries (morning/afternoon/evening/night/daily/weekly/monthly)

**Deduplication**: Three approaches — semantic (timeframe/keyword grouping), topic-based (DBSCAN clustering + LLM merge), and legacy.

9 tables: `user_messages`, `memories`, `memory_tags`, `memory_category`, `memory_topics`, `topics`, `summaries`, `heatmap_score`, `heatmap_memories`.

### 🔁 Proxy

Sole LLM gateway. All LLM communication goes through here.

**Providers**: OpenAI, Anthropic (OpenAI-compat endpoint), Ollama (local). All dispatch is synchronous (queue system was removed).

**Mode resolution**: Modes defined in config.json → resolved to provider/model/options. Modes: `default`, `work`, `claude`, `nsfw`, `router`, etc.

**Prompt system**: Two-tier — centralized (JSON context + Jinja2 templates at `/app/config/prompts/`) preferred, legacy Python modules as fallback.

**Tool support**: Tools passed through to OpenAI/Anthropic. Ollama ignores tools. `tool_choice="auto"` hardcoded.

### ⏱ Scheduler

APScheduler-backed job scheduler with SQLite persistence.

- Brain creates jobs, scheduler fires HTTP callbacks when due
- Supports date (one-off), interval, and cron triggers
- No business logic — just triggers brain based on time

### 🏠 Smarthome

Natural language smart home control via Home Assistant WebSocket API.

**Three-phase LLM pipeline**:
1. Device matching (LLM classifies intent and matches devices)
2. Context building (fetch states, effects/scenes, related devices)
3. Action generation + execution (LLM generates HA service calls)

Also includes media consumption tracking (play/pause/stop events from HA automations, preference aggregation).

Device overrides in `lighting.json` define effects/scenes for 11 light devices.

### 🗒️ Stickynotes

Persistent reminders that surface during agent interactions (never as push notifications).

- SQLite-backed with create/list/check/resolve/snooze
- Brain injects due notes as simulated tool calls before LLM processing
- Supports one-time and recurring (ISO 8601 intervals)
- **Note**: Google Tasks replacement exists in googleapi but migration never completed

### 🗣️ STT/TTS

Speech-to-text and text-to-speech. Runs on host (not containerized) due to hardware requirements.

- TTS via ChatterboxTTS with voice/model options and live playback
- STT via Vosk/Whisper
- REST API + OpenAI-compatible endpoints

## 🔄 System Data Flow

### 📨 Message Processing

```
Platform (Discord/iMessage/API/Gmail)
  → Platform service (contact resolution, message extraction)
  → Brain /api/multiturn
    → Ledger sync (message buffer)
    → Pre-brainlets (memory search → heatmap update → memory injection)
    → Proxy /api/multiturn (mode → provider/model resolution → system prompt → LLM)
    → Tool loop (if tool_calls: execute → sync to ledger → repeat, max 10)
    → Post-brainlets
    → Ledger sync (assistant response)
  → Response back to platform service
  → Reply to user
```

### 🔔 Notification Flow

```
Scheduler fires job callback
  → Brain /notification/execute
  → Check user activity (last_seen)
  → Fetch contact details
  → Route: iMessage (preferred) or Discord DM
```

### 🔥 Memory Heat Calculation

```
Conversation messages arrive
  → memory_search brainlet extracts keywords via LLM
  → POST to ledger /context/update_heatmap with weighted keywords
  → Ledger updates keyword scores (reinforce/adjust/decay)
  → Ledger rescores all memories against updated heatmap
  → GET ledger /context/?limit=5 returns top contextual memories
  → Memories injected into conversation before LLM call
```

## ⚙️ Configuration

- **Service configs**: `~/.kirishima/config.json` (mounted as `/app/config` in containers)
- **Ports**: All defined in `.env`, referenced as `${SERVICE_PORT}` in docker-compose
- **Service discovery**: Container names on `shared-net` Docker network
- **Prompt templates**: Centralized at `~/.kirishima/prompts/` (Jinja2)
- **MCP access control**: `/app/config/mcp_clients.json` (host path `~/.kirishima/mcp_clients.json`)

## ⚠️ Known Architectural Issues

1. **Stickynotes migration incomplete** — Google Tasks backend built in googleapi but brain still uses standalone SQLite service. APIs are incompatible.

2. **"Summarize" service referenced in old docs doesn't exist** — Summary generation is handled by ledger directly.

3. **Queue system removed but docs reference it** — Proxy dispatch is now synchronous. Old references to async queues, workers, and priority dispatch are outdated.

4. **Proxy legacy prompt modules broken** — `guest.py` and `work.py` have wrong import paths after refactor. Centralized system works, but fallback crashes.

5. **Brain tool_calls truncation** — Only first tool call preserved from multi-tool LLM responses.

6. **No streaming support** — All LLM calls set `stream=False` despite config options.

7. **Smarthome has critical bugs** — Infinite recursion in area route, duplicate media routes, undefined variable in error handler.

8. **Discord/iMessage error handling** — Both raise HTTPException in contexts where it's not appropriate (Discord event handlers, BlueBubbles webhook receivers).
