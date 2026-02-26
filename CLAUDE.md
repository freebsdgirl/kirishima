# Kirishima - Claude Code Instructions

## What This Project Is

Kirishima is a modular, microservice-based personal assistant. The **brain** service orchestrates everything, routing messages and managing context. Services communicate via HTTP APIs only — never access another service's DB directly.

All services run in Docker containers except `stt_tts` and `divoom` (hardware constraints). Docker auto-restarts on code changes — **never restart Docker containers or the Docker daemon manually**.

## Project Layout

```
services/          # Each microservice has its own directory, Dockerfile, and README
  brain/           # Central orchestrator — routes, recalls, manages context and tools
  proxy/           # LLM gateway — prompt construction, model/provider resolution, queueing
  ledger/          # Persistent message/memory store — SQLite, cross-platform conversation history
  api/             # OpenAI-compatible REST API front-end
  contacts/        # User/contact management, cross-platform ID resolution
  scheduler/       # Cron-like job/reminder triggering
  discord/         # Discord DM bridge
  imessage/        # BlueBubbles iMessage integration
  googleapi/       # Gmail integration (OAuth2)
  stickynotes/     # Persistent context-aware reminders
  smarthome/       # Home Assistant / natural language device control
  divoom/          # Bluetooth emoji display (runs on host, not containerized)
  stt_tts/         # Speech-to-text / text-to-speech (runs on host, not containerized)
shared/            # Shared utilities, models, config — mounted into all containers
docs/              # Architecture docs, ADRs, planning docs
docker-compose.yml # Service definitions, all ports via .env variables
```

## Hard Rules

1. **Services communicate via HTTP only.** No direct DB access across services.
2. **Brain never talks to LLMs directly.** Always goes through proxy.
3. **Proxy is the only service that talks to LLMs.** Prompt construction, model selection, streaming — all proxy.
4. **All data persistence uses SQLite** (WAL mode, foreign keys enabled).
5. **Never restart Docker containers or the daemon.** Code changes trigger auto-restart. If it looks like a restart didn't happen, wait — Randi will intervene.
6. **Use the shared logging module everywhere:**
   ```python
   from shared.log_config import get_logger
   logger = get_logger(f"brain.{__name__}")  # Replace "brain" with the service name
   ```

## Key Architecture Patterns

### LLM Mode/Model/Provider System (proxy)
- **Modes** (`default`, `work`, `claude`, `nsfw`): Abstract configs mapping to use cases
- **Providers** (`openai`, `anthropic`, `ollama`): Each has its own queue + worker
- **Resolution**: `resolve_model_provider_options(mode)` in `proxy/app/util.py`
- **Prompt modules**: `services/proxy/app/prompts/{provider}-{mode}.py`, dispatched by `dispatcher.py`
- Request flow: Service requests mode → proxy resolves provider/model → dispatcher finds prompt module → provider queue → worker → normalized response

### Memory System (ledger)
- Heatmap-based, not vector DB. Keywords get dynamic multipliers (0.1x-1x) that decay based on conversation patterns.
- Memory search uses AND logic with multiple filters (keywords, categories, topics, time ranges).
- Context heatmap: keywords scored as high/medium/low, with reinforcement/decay cycles.

### Message Flow
- All messages (user/assistant/system/tool) logged in ledger
- Cross-platform continuity — Discord, iMessage, Gmail, API all feed one conversation thread
- Sync endpoint handles dedup, in-place editing, tool call preservation

### Brain Orchestration
- Brainlets: modular pre/post-processing pipeline
- Tool invocation: brain manages tool calls, dispatches to relevant services
- Self-modifying prompts: `manage_prompt` tool writes to SQLite, injected into system prompt

## Config & Environment

- Service configs: `~/.kirishima/config.json` (mounted as `/app/config` in containers)
- Ports: All defined in `.env`, referenced as `${SERVICE_PORT}` in docker-compose
- Service discovery: Services reference each other by container name on `shared-net` Docker network
- Prompt templates: Jinja2 templates in `services/proxy/app/prompts/`

## Development Workflow

- `docker-compose up <service>` to run individual services
- No monolithic test runner — test services in isolation via HTTP
- Each service has a README with endpoint details — **read it before modifying the service**
- Logs: per-service, routed to Graylog via GELF

## Style Guide

- Conversational, concise, senior-engineer pragmatic
- Answer the core question first, then details
- No filler openings ("Certainly", "I'm happy to help", etc.)
- No performative apologies
- Short paragraphs, tight bullet lists
- State assumptions explicitly when inferring

## Detailed Documentation

For deeper dives, see:
- `docs/Full Architecture.md` — architectural principles and service details
- `services/*/README.md` — per-service endpoint docs and implementation details
- `.github/copilot-instructions.md` — original detailed instructions (includes ledger schema, provider system details)
