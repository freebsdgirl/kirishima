# Copilot Instructions for the Kirishima Codebase

## Overview & Architecture
- **Kirishima** is a modular, multi-service personal assistant system. The core orchestrator is the `brain` service, which routes, recalls, and manages context, backed by microservices for memory, messaging, scheduling, reminders, and more.
- Services communicate via HTTP APIs, with strict boundaries: e.g., `brain` never talks to LLMs directly, but always via `proxy` or `api`.
- All persistent data (messages, memories, topics, summaries) is stored in SQLite databases, one per service.
- Most services run in Docker containers. Notable exceptions: `stt_tts` (speech) and `divoom` (Bluetooth display) run outside Docker due to hardware constraints.

## Microservices (see `services/` directory)
- **brain**: Orchestrates chat, memory, tool invocation, notifications, and scheduler jobs. Implements modular "brainlets" for pre/post-processing. All cross-service coordination flows through here.
- **proxy**: LLM gateway. Handles prompt construction, model/provider resolution, and async queueing for OpenAI/Anthropic/Ollama. Prompts are built using Jinja templates and provider/mode-specific modules in `app/prompts/`. Implements provider-specific queues and workers for parallel processing.
- **ledger**: Comprehensive persistent data store for messages, memories, topics, summaries, and contextual heatmaps. Implements advanced message synchronization with deduplication, in-place editing, and conflict resolution. Features include: multi-parameter memory search with AND logic filtering, topic-based conversation threading, temporal summary management, platform-agnostic storage across API/Discord/iMessage with tool call preservation, and dynamic keyword heatmap system for contextual memory scoring.
- **contacts**: Manages user/contact info and cross-platform IDs.
- **scheduler**: Triggers jobs and reminders, often by calling endpoints on `brain`.
- **api**: OpenAI-compatible REST API front-end, handles prompt routing and model modes.
- **discord**: Bridges Discord DMs to the system, syncing users and forwarding messages via `brain`.
- **imessage**: Integrates with BlueBubbles to send/receive iMessages, forwarding to `brain`.
- **googleapi**: Gmail integration providing email sending, receiving, searching, and monitoring with OAuth2 authentication.
- **stickynotes**: Persistent, context-aware reminders surfaced only during agent interaction.
- **smarthome**: Handles device/entity discovery and natural language smart home requests.
- **divoom** (not containerized): Bluetooth emoji/status display, run on host for hardware access.
- **stt_tts** (not containerized): Speech-to-text and text-to-speech stack, run on host for audio hardware.
- **ollama**, **ollama-webui**: LLM model hosting and web UI (details in respective directories).

## Developer Workflows
- **Run/build**: Use `docker-compose` for local development. Each service has its own Dockerfile and can be run independently for debugging. `stt_tts` and `divoom` must be run manually on the host.
- **Testing**: No monolithic test runner; test each service in isolation. Use HTTP requests (e.g., with `httpx` or curl) to exercise endpoints.
- **Debugging**: Logs are written per-service. Check logs in each container for troubleshooting. Most errors are surfaced as HTTP 4xx/5xx with detailed logs.
- **Configuration**: All service configs are in `/app/config/config.json` (or similar per-service). Model/provider mappings for LLMs are in `proxy`'s config.

## Project-Specific Patterns
- **Prompt Construction**: Prompts for LLMs are not hardcoded; they're built from context (memories, summaries, time, etc.) and rendered via Jinja templates. See `services/proxy/app/prompts/`.
- **Memory & Message Flow**: All user/assistant/system/tool messages are logged in `ledger`. Memories are extracted and stored via dedicated endpoints, not inline in chat logic.
- **Service Boundaries**: Never bypass service APIs (e.g., don't access another service's DB directly). Always use HTTP endpoints for cross-service data.
- **Error Handling**: All HTTP errors are logged and surfaced as FastAPI `HTTPException` with appropriate status codes and details.
- **Extensibility**: To add a new integration, create a new service and expose its API. Register it in the main config and orchestrate via `brain`.

## Ledger Service Technical Details

### Database Architecture
The ledger service uses SQLite with WAL mode and foreign key constraints for data integrity. Core tables include:
- **`user_messages`**: Platform-agnostic message storage with tool call support and topic associations
- **`memories`**: Long-term knowledge with access tracking (`access_count`, `last_accessed`, `reviewed` status)
- **`memory_tags`**: Many-to-many keyword associations for semantic search
- **`memory_category`**: One-to-one category assignments per memory
- **`memory_topics`**: Many-to-many memory-to-topic relationships for conversation threading
- **`topics`**: UUID-based topic storage with names and creation timestamps
- **`summaries`**: Temporal summary storage with metadata (`timestamp_begin`, `timestamp_end`, `summary_type`)
- **`heatmap_score`**: Dynamic keyword scoring for contextual relevance (score, last_updated)
- **`heatmap_memories`**: Cached memory scores based on keyword matches for fast contextual retrieval

### Message Synchronization Logic
The `/user/{user_id}/sync` endpoint implements complex synchronization rules:
1. **Deduplication**: Identical consecutive user messages are removed
2. **Assistant Editing**: In-place content updates when assistant responses change
3. **Consecutive User Handling**: Resolves server error scenarios with message rollback
4. **Platform Logic**: Different handling for API vs. external platform messages (Discord, iMessage)
5. **Tool Call Preservation**: Maintains `tool_calls`, `function_call`, and `tool_call_id` data
6. **Buffer Integrity**: Ensures buffers always start with user messages

### Memory Search System
Advanced search capabilities with multiple combined filters using AND logic:
- **Keywords**: Multi-keyword matching with configurable minimum thresholds and progressive fallback
- **Categories**: Single category filtering for organizational structure
- **Topic Association**: Search memories linked to specific conversation topics
- **Time Filtering**: Created before/after timestamp ranges for temporal queries
- **Memory ID**: Direct lookup bypassing other filters
- **Search Algorithm**: Intersection-based filtering ensuring all conditions match, with efficient indexing

### Context Heatmap System  
Dynamic keyword relevance tracking for contextual memory scoring:
- **Weight Categories**: Keywords classified as "high" (1.0), "medium" (0.7), or "low" (0.5) scores
- **Score Evolution**: Keywords adjust based on reinforcement (10% boost), decay (0.08 per cycle), and removal (below 0.1)
- **Memory Scoring**: Real-time calculation of memory relevance as sum of matching keyword scores
- **Contextual Retrieval**: `/context/` endpoint provides most relevant memories based on current heatmap
- **API Endpoints**: `/context/update_heatmap` (POST), `/context/top_memories` (GET), `/context/keyword_scores` (GET)
- **Use Cases**: Conversation context injection, dynamic memory prioritization, adaptive learning patterns

### Configuration Parameters
- **`ledger.turns`**: Default message history limit (default: 15)
- **`db.ledger`**: SQLite database file path
- **`tracing_enabled`**: Optional distributed tracing support

### Key Utilities
- **`_open_conn()`**: Standard SQLite connection with WAL mode and foreign keys enabled
- **`get_period_range()`**: Time period parsing for temporal filtering (night, morning, afternoon, evening, day)
- **`_find_or_create_topic()`**: Topic deduplication preventing duplicate names
- **`ensure_first_user()`**: Message buffer validation ensuring user-first ordering

### Data Models
- **`RawUserMessage`**: Incoming message format with platform metadata
- **`CanonicalUserMessage`**: Server-side canonical format with IDs and timestamps
- **`MemoryEntry`**: Unified memory model supporting creation, search, and updates
- **`MemorySearchParams`**: Multi-parameter search request with combinatorial logic
- **`Summary`** with **`SummaryMetadata`**: Temporal summary storage with typed periods

## LLM Mode/Model/Provider System
The proxy service implements a sophisticated multi-provider LLM system with three key concepts:

### **Modes**
- **Purpose**: Abstract configurations that map to specific use cases (e.g., "default", "work", "claude", "nsfw")
- **Configuration**: Defined in `config.json` under `llm.mode.{mode_name}`
- **Usage**: Services request by mode name, not by specific model/provider
- **Example modes**: `default` (gpt-4o), `work` (gpt-4.1), `claude` (claude-sonnet-4-20250514), `nsfw` (nemo:latest)

### **Providers**
- **Supported**: `openai`, `anthropic`, `ollama`
- **Implementation**: Each provider has its own queue, worker, and request/response models
- **Queues**: `openai_queue`, `anthropic_queue`, `ollama_queue` in `proxy/app/queue/router.py`
- **Workers**: Provider-specific functions (`send_to_openai()`, `send_to_anthropic()`, `send_to_ollama()`) in `proxy/app/queue/worker.py`
- **Models**: `OpenAIRequest/Response`, `AnthropicRequest/Response`, `OllamaRequest/Response` in `shared/models/proxy.py`

### **Model Resolution**
- **Function**: `resolve_model_provider_options(mode)` in `proxy/app/util.py`
- **Process**: Mode → (provider, model, options) → Provider-specific queue
- **Fallback**: Falls back to "default" mode if requested mode not found
- **API Keys**: Retrieved from config.json per provider (`openai.api_key`, `anthropic.api_key`)

### **Prompt Modules**
- **Naming Convention**: `{provider}-{mode}.py` (e.g., `openai-default.py`, `anthropic-default.py`, `ollama-nsfw.py`)
- **Location**: `services/proxy/app/prompts/`
- **Dispatcher**: `app/prompts/dispatcher.py` tries `{provider}-{mode}`, then `{provider}-default`, then `openai-default`
- **Function**: Each module exports `build_prompt(request)` that returns context for Jinja rendering

### **Adding New Providers**
1. **Add mode to config.json**: Define provider, model, and options
2. **Create request/response models**: Add to `shared/models/proxy.py`
3. **Add queue**: Create new queue in `proxy/app/queue/router.py`
4. **Implement worker**: Add `send_to_{provider}()` function in `proxy/app/queue/worker.py`
5. **Update APIs**: Add provider support to `proxy/app/api/multiturn.py` and `singleturn.py`
6. **Create prompt module**: Copy existing prompt file (e.g., `cp openai-default.py provider-default.py`)
7. **Start worker**: Add to app startup in `proxy/app/app.py`

### **Request Flow**
1. Service requests with mode (e.g., `{"model": "claude"}`)
2. `resolve_model_provider_options()` maps mode → (anthropic, claude-sonnet-4-20250514, options)
3. Dispatcher finds appropriate prompt module (`anthropic-default.py`)
4. Request routed to provider-specific queue (`anthropic_queue`)
5. Worker sends to provider API endpoint
6. Response normalized back to `ProxyResponse`

## Examples & References
- See `/home/randi/kirishima/README.md` for the big-picture vision and service table.
- See `/home/randi/kirishima/services/brain/README.md` for orchestration and endpoint details.
- See `/home/randi/kirishima/services/proxy/README.md` for LLM prompt and queueing logic.
- See `/home/randi/kirishima/services/ledger/README.md` for message/memory schema and API.
- Prompt modules: `services/proxy/app/prompts/`
- Config examples: `shared/config.json.example`, per-service `config.json`

---

If you are unsure about a workflow or pattern, check the relevant service's README or config file for details. When in doubt, prefer explicit, API-driven integration and keep logic modular.
