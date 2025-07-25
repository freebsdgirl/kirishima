"""
This module initializes and configures the FastAPI application for the proxy service.

It includes the following routers:
- `routes_router`: Handles system-level routes.
- `docs_router`: Provides API documentation routes.
- `models_router`: Manages API endpoints related to models.
- `singleturn_router`: Handles single-turn API interactions.
- `multiturn_router`: Handles multi-turn API interactions.
- `imessage_router`: Manages iMessage-related API endpoints.

Tracing:
- If tracing is enabled (`shared.config.TRACING_ENABLED`), the application sets up
    tracing using the `setup_tracing` function from the `shared.tracing` module.

Dependencies:
- FastAPI is used to create the application and manage routing.
- Shared configurations and tracing utilities are imported from the `shared` module.
"""

from app.routes.openai import router as openai_router
from app.routes.queue import router as queue_router

from app.services.queue import ollama_queue, openai_queue, anthropic_queue, queue_worker_main

from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from shared.models.middleware import CacheRequestBodyMiddleware
from fastapi import FastAPI

import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start a worker for each provider-specific queue
    ollama_worker = asyncio.create_task(queue_worker_main(ollama_queue))
    openai_worker = asyncio.create_task(queue_worker_main(openai_queue))
    anthropic_worker = asyncio.create_task(queue_worker_main(anthropic_queue))
    yield
    ollama_worker.cancel()
    openai_worker.cancel()
    anthropic_worker.cancel()
    try:
        await ollama_worker
    except asyncio.CancelledError:
        pass
    try:
        await openai_worker
    except asyncio.CancelledError:
        pass
    try:
        await anthropic_worker
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])

app.include_router(openai_router, tags=["openai"])
app.include_router(queue_router, tags=["queue"], prefix="/queue")

register_list_routes(app)

import json
with open('/app/config/config.json') as f:
    _config = json.load(f)
if _config['tracing_enabled']:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="proxy")