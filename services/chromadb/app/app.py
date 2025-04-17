"""
This module initializes and configures the FastAPI application for the ChromaDB service.

It includes the following routers:
- `routes_router`: Handles system-level routes.
- `docs_router`: Handles documentation-related routes, accessible under the `/docs` prefix.
- `memory_router`: Handles memory-related routes, accessible under the `/memory` prefix.
- `summarize_router`: Handles summarization-related routes, accessible under the `/summary` prefix.
- `buffer_router`: Handles buffer-related routes, accessible under the `/buffer` prefix.

Tracing:
- If tracing is enabled (`shared.config.TRACING_ENABLED`), the application sets up
    tracing using the `setup_tracing` function from the `shared.tracing` module.

Dependencies:
- FastAPI is used to create the application and manage routing.
- Shared configurations and tracing utilities are imported from the `shared` module.
"""

from app.memory import router as memory_router
from app.summarize import router as summarize_router
from app.buffer import router as buffer_router
from app.docs import router as docs_router
from shared.routes import router as routes_router
from app.embedding import router as embedding_router


from fastapi import FastAPI
app = FastAPI()
app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, prefix="/docs", tags=["docs"])
app.include_router(embedding_router, tags=["embedding"])
app.include_router(memory_router, prefix="/memory", tags=["memory"])
app.include_router(summarize_router, prefix="/summary", tags=["summary"])
app.include_router(buffer_router, prefix="/buffer", tags=["buffer"])


import shared.config
if shared.config.TRACING_ENABLED:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="chromadb")
