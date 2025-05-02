# 🧠 Brain Microservice

## Purpose

Brain is the central orchestrator of the Kirishima architecture. It coordinates all inter-service logic including contact resolution, memory embedding, reply generation, and system status management. No other service is permitted to call external endpoints directly—Brain mediates all LLM access, memory reads/writes, and platform-specific communication.

## How It Works

- The service is built with FastAPI and starts by initializing the application instance.
- Middleware is added to cache the request body for downstream access.
- Routers are registered for each functional area: memory (creation, listing, semantic search), mode, scheduler, message handling (multi-turn and single-turn), models, embedding, documentation, and system health.
- Each router defines endpoints that validate input, coordinate with external services (like ChromaDB, Proxy, or Scheduler), and return structured responses.
- If tracing is enabled in the configuration, distributed tracing is set up for observability.
- The service does not handle buffer management, and all LLM/model operations are routed through the Proxy service.

## Port

- 4207

## Main Endpoints

### Message Routing

- `POST /api/multiturn`  
  Handles multi-turn user messages, including context retrieval, memory, and reply generation.
- `POST /api/singleturn`  
  Handles stateless, single-turn user messages.

### Memory Management

- `POST /memory`  
  Create a new memory with embedding.
- `GET /memory`  
  List recent memories for a specific component.
- `DELETE /memory`  
  Delete a memory (bulk or by filter).
- `GET /memory/semantic`  
  Semantic search for memory entries.

### Scheduler Integration

- `POST /scheduler/job`  
  Schedule a new job in the external scheduler.
- `GET /scheduler/job`  
  List all currently scheduled jobs.
- `DELETE /scheduler/job/{job_id}`  
  Delete a scheduled job by ID.
- `POST /scheduler/callback`  
  Callback from Scheduler to execute a registered function.

### System Mode

- `GET /mode`  
  Returns current system mode (e.g., “chat”, “dev”, “proxy_default”).
- `POST /mode/{mode}`  
  Sets the system mode.

### Models & Embeddings

- `GET /models`  
  List available models (proxied from Proxy/Ollama).
- `GET /model/{model_name}`  
  Get details for a specific model.
- `POST /embedding`  
  Generate an embedding for a given input.

### Platform Integrations

- `POST /discord/message/incoming`  
  Handle incoming Discord direct messages.
- `POST /imessage/incoming`  
  Handle incoming iMessage messages.

### Summaries

- `POST /summary/combined/daily`  
  Generate or retrieve a daily summary.
- `POST /summary/combined/weekly`  
  Generate or retrieve a weekly summary.
- `POST /summary/combined/monthly`  
  Generate or retrieve a monthly summary.
- `POST /summary/create`  
  Create a summary (periodic or custom).

### System & Docs

- `GET /ping`  
  Health check.
- `GET /__list_routes__`  
  List all registered API routes.
- `GET /docs/export`  
  Export internal documentation for the Brain service.

## Architecture

- **Framework:** FastAPI

- **Routers:**  
  - `modes_router` – System mode endpoints  
  - `scheduler_router` – Scheduler job endpoints  
  - `memory_functions_router` – Memory creation/deletion  
  - `memory_list_router` – Memory listing/search (including semantic search)  
  - `message_multiturn_router` – Multi-turn message handling  
  - `message_singleturn_router` – Single-turn message handling  
  - `models_router` – Model listing/details  
  - `embedding_router` – Embedding generation  
  - `routes_router` – System endpoints (`/ping`, `/__list_routes__`)  
  - `docs_router` – Documentation export endpoint  
  - `discord_dm_router` – Discord direct message endpoints  
  - `imessage_router` – iMessage endpoints  
  - `daily_summary_router` – Daily summary endpoints  
  - `weekly_summary_router` – Weekly summary endpoints  
  - `monthly_summary_router` – Monthly summary endpoints  
  - `periodic_summary_router` – Periodic summary endpoints

- **Middleware:**  
  - `CacheRequestBodyMiddleware` (from `shared.models.middleware`)  
    Caches the raw request body for downstream access.

- **Dynamic Route Registration:**  
  - `register_list_routes` utility adds a `/__list_routes__` endpoint for route introspection.

- **Tracing:**  
  If `TRACING_ENABLED` is set in config, distributed tracing is enabled via `shared.tracing.setup_tracing`.

- **Extensibility:**  
  The application is modular, allowing easy integration of additional routers and middleware.

## Responsibilities

- Orchestrate all inter-service logic and dispatch, acting as the central coordinator for the Kirishima architecture.
- Manage memory, summary (daily, weekly, monthly, periodic), mode, and scheduling pipelines.
- Route all LLM and model requests through the Proxy service, ensuring no direct external calls from other services.
- Mediate platform-specific communication, including Discord DMs and iMessage endpoints.
- Expose system health, mode, documentation export, and route introspection endpoints for monitoring and developer access.
- Apply middleware for request body caching to support downstream processing.
- Enable distributed tracing for observability when configured.

## Known Issues

- All logic is linear and blocking unless offloaded to the Scheduler.

## External Dependencies

- Proxy (model and request routing)
- ChromaDB (semantic memory)
- Contacts (identity resolution)
- Intents (message interpretation)
- Ledger (chatlog)
- Scheduler (job management)
