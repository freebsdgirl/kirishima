# 🧠 Brain Microservice

## Purpose

Brain is the central orchestrator of the Kirishima architecture. It coordinates all inter-service logic including contact resolution, memory embedding, reply generation, and system status management. No other service is permitted to call external endpoints directly—Brain mediates all LLM access, memory reads/writes, and platform-specific communication.

## How It Works

- The service is built with FastAPI and starts by initializing the application instance.
- Middleware is added to cache the request body for downstream access.
- Routers are registered for each functional area: memory (creation, listing, semantic search), mode, scheduler, message handling (multi-turn and single-turn), models, embedding, documentation, and system health.
- Each router defines endpoints that validate input, coordinate with external services (like ChromaDB, Proxy, or Scheduler), and return structured responses.
- If tracing is enabled in the configuration, distributed tracing is set up for observability.
- The service does not handle buffer management or summarization logic, and all LLM/model operations are routed through the Proxy service.

## Port

- **4207** (default)

## Main Endpoints

### Message Routing

- `POST /message/multiturn/incoming`  
  Handles multi-turn user messages, including context retrieval, memory, and reply generation.
- `POST /message/single/incoming`  
  Handles stateless, single-turn user messages.

### Memory Management

- `POST /memory`  
  Create a new memory with embedding.
- `GET /memory`  
  List recent memories for a specific component.
- `GET /memory/{id}`  
  Retrieve a specific memory by ID.
- `DELETE /memory/{id}`  
  Delete a memory by ID.
- `PUT /memory/{id}`  
  Replace an entire memory.
- `PATCH /memory/{id}`  
  Partially update a memory.
- `POST /memory/search/id`  
  Return the ID of a memory that matches the input string.
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

- **Middleware:**  
  - `CacheRequestBodyMiddleware` (from `shared.models.middleware`)  
    Caches the raw request body for downstream access.

- **Tracing:**  
  If `TRACING_ENABLED` is set in config, distributed tracing is enabled via `shared.tracing.setup_tracing`.

## Shared Classes & Utilities

- **CacheRequestBodyMiddleware:**  
  Middleware to cache the request body for multiple reads during request processing.

- **register_list_routes:**  
  Utility to add a `/__list_routes__` endpoint for route introspection.

## Responsibilities

- Orchestrate all inter-service logic and dispatch.
- Manage memory, mode, and scheduling pipelines.
- Route all LLM and model requests through Proxy.
- Expose system health, mode, and documentation endpoints.

## Known Issues

- All logic is linear and blocking unless offloaded to the Scheduler.

## External Dependencies

- Proxy (model and request routing)
- ChromaDB (semantic memory)
- Contacts (identity resolution)
- Scheduler (job management)
