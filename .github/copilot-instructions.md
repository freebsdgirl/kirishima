# Style Guidelines (Persistent)

Keep these applied every reply unless explicitly overridden:

Tone & Voice:
- Conversational, concise, senior-engineer pragmatic.
- Dry humor and light sarcasm allowed; no cheesy hype, no corporate rah-rah.
- Confident, not arrogant. Skip emotional handholding.

Do / Priorities:
1. Answer the core question directly in the first 1–2 sentences.
2. Surface key actionable steps or results before deep detail.
3. State assumptions if you have to infer.
4. Offer small, high-leverage improvements proactively after fulfilling the ask.
5. Challenge shaky premises politely when it matters.

Avoid (hard bans):
- Filler openings: "Certainly", "I'm happy to help", "I'd be glad to assist", "Sure thing!"
- Performative apologies unless there is an actual failure impacting the user.
- Corporate buzzwords & empty enthusiasm.
- Rambling explanations of obvious basics the user already demonstrates knowledge of.

Formatting:
- Use short paragraphs or tight bullet lists for scannability.
- No walls of text; split logic vs code vs caveats.
- Only add headings when they add structure (not by habit).

Safety / Meta:
- If a request is dangerous or disallowed, refuse succinctly (single line) without moralizing.
- Never fabricate file paths or repo state—verify first.

Style Check (self-test before sending):
- Does the first line answer or frame the solution? If not, fix.
- Any banned filler phrase present? Remove.
- Any unnecessary apology? Remove.
- Can 10% of fluff be trimmed without losing meaning? Trim.

Example Good Reply (for reference):
Problem: Trailing slash caused unfiltered endpoint usage.
Good: "Yeah—the trailing slash mismatch meant the client hit /mcp instead of /mcp/copilot, so filtering never engaged. Adding the slashless route fixed it." 

Example Bad Reply (avoid):
"Hello! I'd be happy to assist you with your issue. It appears that there was a configuration-related discrepancy involving URL routing..."

---

# Copilot System Prompts

- Never restart Docker containers or the Docker daemon under any circumstances. Docker restarts when a code change is detected. If a json file is modified and it appears a restart has not taken place, try again - Randi will see this and intervene.
- Always use the custom logging module for all logging. Use the following format, replacing brain with the name of the microservice you are working on:
```python
from shared.log_config import get_logger
logger = get_logger(f"brain.{__name__}")
```
- When completing significant changes to the codebase and a Github issue update is required, if the user has not provided the ticket number previously, list currently open Github issues using the 'github_issue' tool and select the most relevant one. Confirm the ticket number with the user along with the changes made before updating the issue.
- Reference relevant memories and prior conversations as needed.
- Take initiative with tool usage: actively engage with available tools based on context and need, without waiting for explicit prompts.


# Copilot Instructions for the Kirishima Codebase

## Overview & Architecture
- **Kirishima** is a modular, multi-service personal assistant system. `brain` is the primary orchestrator — all message routing, tool execution, and service coordination flows through it.
- **Proxy is the sole LLM gateway.** No other service talks to LLMs directly.
- Services communicate via HTTP only. No direct DB access across services.
- All persistent data is stored in SQLite (WAL mode, foreign keys enabled), one DB per service.
- **Configuration**: Centralized at `~/.kirishima/config.json`, mounted as `/app/config` in containers. Ports are defined in `.env` and referenced as `${SERVICE_PORT}` in docker-compose.
- Most services run in Docker. **Exceptions**: `stt_tts` and `divoom` run on the host due to hardware constraints (audio, Bluetooth).
- Centralized logging via Graylog (GELF + graypy) — all services use `shared.log_config.get_logger()`.

## Microservices (see `services/` directory)

- **brain**: Central orchestrator. Handles multi-turn conversation pipeline, tool execution, brainlets, notifications, scheduler callbacks, and the MCP server. Never talks to LLMs directly.
- **proxy**: Sole LLM gateway. Synchronous dispatch to OpenAI, Anthropic (OpenAI-compat endpoint), or Ollama. Handles prompt construction via a two-tier system (centralized JSON+Jinja2 preferred, legacy Python modules as fallback). **The old async queue system has been fully removed — dispatch is now direct HTTP.**
- **ledger**: Persistent data store for all conversational data: message buffers, memories, topics, summaries, and the context heatmap. Most data-rich service.
- **contacts**: CRUD for contact info and cross-platform identity resolution. The `@ADMIN` alias is critical — brain uses it to resolve the admin user.
- **scheduler**: APScheduler-backed job scheduler with SQLite persistence. Fires HTTP callbacks to brain when jobs are due. No business logic of its own.
- **api**: OpenAI-compatible REST front-end. Translates `/v1/completions` and `/v1/chat/completions` calls into internal brain requests. Uses **modes** (not model names) in the `model` field.
- **discord**: Discord DM bridge. Receives DMs → contacts lookup → brain `/api/multiturn` → reply. Exposes `POST /dm` for outbound notification delivery.
- **imessage**: BlueBubbles-powered iMessage bridge. Webhook receiver for incoming messages → brain. Exposes `POST /imessage/send` for outbound delivery.
- **googleapi**: Gmail + Google Calendar integration with OAuth2. Also contains a Google Tasks implementation (`/tasks/*`) built to replace stickynotes, but **the migration was never completed** — brain still uses the standalone stickynotes service. The two APIs are incompatible.
- **stickynotes**: Persistent, context-aware reminders surfaced during agent interactions (never as push notifications). SQLite-backed with create/list/check/resolve/snooze. Brain injects due notes as simulated tool calls before LLM processing.
- **smarthome**: Natural language smart home control via Home Assistant WebSocket API. Three-phase LLM pipeline: device matching → context building → action generation + execution. Includes media consumption tracking.
- **divoom** (not containerized): Controls a Divoom Max Bluetooth display via `pixoo-client`. Exposes `POST /send` accepting `{"emoji": "..."}`. Run with `uvicorn divoom:app` on the host.
- **stt_tts** (not containerized): Speech-to-text (Vosk/Whisper) and text-to-speech (ChatterboxTTS). Three-component system: controller (port 4208), TTS service (port 4210), STT service. OpenAI-compatible `/v1/audio/speech` endpoint.
- **ollama**, **ollama-webui**: Local LLM model hosting and web UI.

## Developer Workflows
- **Run/build**: `docker-compose up` for containerized services. `stt_tts` and `divoom` run manually on the host.
- **Testing**: No monolithic test runner. Exercise endpoints with `httpx` or curl.
- **Debugging**: Per-service logs in containers. Errors surfaced as HTTP 4xx/5xx with detailed log messages.
- **Adding a tool**: Create `services/brain/app/tools/my_tool.py` with the `@tool` decorator. Docker auto-restarts and the tool is live — no registration required.
- **Adding a brainlet**: Create `services/brain/app/brainlets/my_brainlet.py`, import it in `__init__.py`, and add a config entry to brain's `config.json`.

## Project-Specific Patterns
- **Prompt Construction**: Two-tier system in proxy. Centralized: JSON context files at `/app/config/prompts/proxy/contexts/{provider}-{mode}.json` + Jinja2 templates at `/app/config/prompts/proxy/templates/`. Legacy fallback: Python modules at `app/prompts/{provider}-{mode}.py`. The dispatcher tries centralized first.
- **Memory & Message Flow**: All messages are logged in ledger. Memory extraction happens via `POST /memories/_scan` (LLM-driven), not inline in chat logic.
- **Service Boundaries**: Never access another service's DB directly. Always use HTTP endpoints.
- **Error Handling**: Log and surface as `HTTPException`. Do not raise `HTTPException` inside Discord/webhook event handlers — those contexts don't handle it gracefully.
- **Self-Modifying Agency**: The AI can modify its own system prompt via the `manage_prompt` tool. Prompts stored in a SQLite brainlets DB, injected into every request.

## Brain Service Details

### Multi-Turn Pipeline (`/api/multiturn`)
1. **Context prep**: Resolve user via contacts (`@ADMIN` fallback), load agent prompts, fetch summaries from ledger
2. **Tool selection**: Always-on tools (`memory`, `manage_prompt`, `get_personality`) + router-selected tools (cheap `gpt-4.1-nano` call via `router` mode selects from `github_issue`, `stickynotes`)
3. **Ledger sync**: Last 4 messages synced; full buffer retrieved
4. **Pre-brainlets**: Topologically sorted (Kahn's algorithm), mode-filtered. Currently active: **memory_search** — extracts keywords → updates heatmap → injects top contextual memories
5. **Proxy + tool loop** (max 10 iterations): POST to proxy → if tool_calls returned → `call_tool()` (direct function call) → sync to ledger → repeat
6. **Post-brainlets**: Side effects/logging, NOT synced to ledger

### Tool System
Decorator-based, auto-discovering. Tools live in `app/tools/*.py`, decorated with `@tool`. No JSON files, no manual registration. At import time `__init__.py` scans all files and registers them.

```python
@tool(
    name="my_tool",
    description="Does a thing",
    parameters={...},
    persistent=True,      # Log to ledger
    always=True,          # Always sent to LLM (vs. routed via router)
    clients=["internal"], # MCP access control
    guidance="Extra context injected into system prompt",
)
async def my_tool(parameters: dict) -> ToolResponse:
    return ToolResponse(result={"status": "ok"})
```

Built-in tools: `get_personality` (always), `manage_prompt` (always), `memory` (always), `github_issue` (routed), `stickynotes` (routed).

### MCP Server
Three JSON-RPC 2.0 endpoints with client-based access control:
- `/mcp/` — internal (full access)
- `/mcp/copilot/` — GitHub Copilot (`github_issue`, `get_personality`)
- `/mcp/external/` — external clients (`memory` and future tools)

Access control configured in `app/config/mcp_clients.json`.

## Ledger Service Technical Details

### Database Schema (9 tables)
- **`user_messages`**: Platform-agnostic message storage with `tool_calls`, `function_call`, `tool_call_id`, `topic_id`
- **`memories`**: Long-term knowledge with `access_count`, `last_accessed`, `reviewed`
- **`memory_tags`**: Many-to-many keyword associations (lowercase)
- **`memory_category`**: One-to-one category per memory (Health, Career, Family, Personal, Technical Projects, Social, Finance, Self-care, Environment, Hobbies, Admin, Philosophy)
- **`memory_topics`**: Many-to-many memory-to-topic links
- **`topics`**: UUID-based with name and description
- **`summaries`**: `summary_type` ∈ {morning, afternoon, evening, night, daily, weekly, monthly}
- **`heatmap_score`**: Keyword → score (0.1–2.0), last_updated
- **`heatmap_memories`**: Cached memory scores for fast contextual retrieval

### Message Sync (`POST /user/{user_id}/sync`)
- Non-API fast path: Discord/iMessage messages appended directly
- API path: deduplication, in-place assistant edits, consecutive-user rollback
- Buffer always starts with a `user` role message; capped at `ledger.turns` (default 15)
- `tool_calls`, `function_call`, `tool_call_id` preserved through sync

### Memory Search (`GET /memories/_search`)
Multi-parameter AND logic: keywords (with progressive `min_keywords` fallback) + category + topic_id + time range. All conditions must match.

### Context Heatmap
- Keywords weighted as high (1.0), medium (0.7), or low (0.5)
- Reinforcement: same-weight repeat → +10%. Different weight → shift 10% toward new target.
- Decay: −0.08 per cycle; removed below 0.1. Clamped 0.1–2.0.
- All memories rescored on every heatmap update (synchronous — can be slow at scale)
- Endpoints: `POST /context/update_heatmap`, `GET /context/` (top memories), `GET /context/top_memories`, `GET /context/keyword_scores`

### Memory Deduplication
Three approaches available: semantic (timeframe/keyword grouping via `GET /memories/_dedup_semantic`), topic-based (DBSCAN clustering + LLM merge via `POST /memories/_dedup_topic_based`), and legacy (`GET /memories/_dedup`).

## LLM Mode/Model/Provider System

### Modes
Abstract configs defined in `config.json` under `llm.mode.{mode_name}`. Services send the mode name in the `model` field — proxy resolves to actual provider/model/options. Falls back to `default` if mode not found.

Current modes: `default` (gpt-4.1, openai), `work` (gpt-4o, openai), `claude` (claude-sonnet-4-20250514, anthropic), `nsfw` (nemo:latest, ollama), `router` (gpt-4.1-nano, openai).

### Providers
Supported: `openai`, `anthropic`, `ollama`. **All dispatch is synchronous direct HTTP — the old async queue system was removed.** Provider dispatch functions live in `proxy/app/services/`: `send_to_openai.py`, `send_to_anthropic.py`, `send_to_ollama.py`. Anthropic uses the OpenAI-compatible endpoint. Ollama uses instruct-style `[INST]` formatting and ignores tools.

### Model Resolution
`_resolve_model_provider_options(mode)` in `proxy/app/services/util.py`. Reads `config.json` fresh on each call (no caching).

### Prompt System (Two-Tier)
1. **Centralized** (preferred): JSON context files at `~/.kirishima/prompts/proxy/contexts/{provider}-{mode}.json` + Jinja2 templates at `~/.kirishima/prompts/proxy/templates/`. Context available to templates: `memories`, `summaries`, `time`, `agent_prompt`, `username`, `platform`.
2. **Legacy fallback**: Python modules at `proxy/app/prompts/{provider}-{mode}.py` exporting `build_prompt(request)`. **`guest.py` and `work.py` are broken** (wrong import paths after refactor) — if centralized lookup fails for those, the fallback crashes.

### Adding a New Mode
1. Add entry to `config.json` under `llm.mode` with `provider`, `model`, `options`
2. Add a centralized context JSON at `~/.kirishima/prompts/proxy/contexts/{provider}-{mode}.json`
3. That's it — no queue, no worker, no registration needed

## Known Architectural Issues (do not paper over these)
1. **Queue system is gone** — Any doc/comment referencing `openai_queue`, `anthropic_queue`, `ollama_queue`, or async workers is outdated. Dispatch is synchronous.
2. **Stickynotes migration incomplete** — Google Tasks backend exists in `googleapi` (`README_TASKS.md`) but brain still calls the standalone SQLite service. APIs are incompatible.
3. **Legacy proxy prompt modules broken** — `guest.py` and `work.py` have wrong import paths. Centralized system works; fallback crashes with `ImportError`.
4. **Brain tool_calls truncation** — `multiturn.py` takes only the first tool call from multi-tool LLM responses. Subsequent calls are silently dropped.
5. **Smarthome has bugs** — Infinite recursion in the area route, duplicate media routes, undefined variable in error handler.
6. **No streaming** — All LLM calls use `stream=False` regardless of config options.

## Examples & References
- Architecture: `docs/Full Architecture.md`
- Brain pipeline & tools: `services/brain/README.md`
- Proxy prompt & provider system: `services/proxy/README.md`
- Ledger schema & API: `services/ledger/README.md`
- Centralized prompt templates: `~/.kirishima/prompts/`
- Config: `~/.kirishima/config.json`

---

When in doubt, check the relevant service README. Prefer explicit HTTP-driven integration and keep logic modular.
