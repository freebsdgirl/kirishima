# 🌐 API Microservice

## Purpose

Acts as the OpenAI-compatible gateway for clients, translating requests into internal service calls (primarily to the Brain service). It manages prompt construction, context injection, memory access, and user interaction scaffolding.

## Port

- **4200** (default)

## Main Endpoints

### Core

- `POST /chat/completions`  
  Multi-turn, stateful chat endpoint. Redirects to `/v1/chat/completions` for OpenAI compatibility. Handles context, memory, and conversation history.
- `POST /v1/chat/completions`  
  Main multi-turn chat endpoint. Integrates with the Brain service for reasoning and memory.
- `POST /completions`  
  Stateless, one-shot completion endpoint for single prompts. Redirects to `/v1/completions`.
- `POST /v1/completions`  
  OpenAI-compatible stateless completion endpoint.

### Models

- `GET /models`  
  Redirects to `/v1/models`. Lists available models (proxied from Brain/Ollama).
- `GET /v1/models`  
  Lists available models in OpenAI-compatible format.
- `GET /models/{model_id}`  
  Redirects to `/v1/models/{model_id}`.
- `GET /v1/models/{model_id}`  
  Get details for a specific model.

### System & Docs

- `GET /ping`  
  Health check.
- `GET /__list_routes__`  
  List all registered API routes.
- `GET /docs/export`  
  Export internal documentation for the API service.

## Architecture

- **Framework:** FastAPI
- **Routers:**  
  - `singleturn_router` – Handles `/completions` endpoints  
  - `multiturn_router` – Handles `/chat/completions` endpoints  
  - `get_model_router` – Handles `/models/{model_id}` and `/v1/models/{model_id}`  
  - `list_models_router` – Handles `/models` and `/v1/models`  
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

- Normalize and proxy OpenAI-compatible API requests.
- Route requests to internal services (primarily Brain).
- Provide model listing and metadata.
- Expose system health and documentation endpoints.

## Known Issues

- Some advanced function-calling and memory features may be handled in downstream services (Brain).
- Mode switching and certain stateful operations are managed outside the API microservice.

## External Dependencies

- Brain (reasoning, memory, model inference)
- Proxy (model and request routing)
- ChromaDB (semantic memory, via Brain)
- Scheduler (job management, via Brain)

