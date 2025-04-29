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

from app.embedding import router as embedding_router

from app.memory.delete import router as memory_delete_router
from app.memory.get_id import router as memory_get_id_router
from app.memory.get_list import router as memory_get_list_router
from app.memory.get_search import router as memory_get_search_router
from app.memory.get_semantic_search import router as memory_get_semantic_search_router
from app.memory.patch import router as memory_patch_router
from app.memory.post import router as memory_post_router
from app.memory.put import router as memory_put_router

from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from shared.models.middleware import CacheRequestBodyMiddleware
from fastapi import FastAPI

app = FastAPI()
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])

app.include_router(embedding_router, tags=["embedding"])

app.include_router(memory_delete_router, tags=["memory"])
app.include_router(memory_get_id_router, tags=["memory"])
app.include_router(memory_get_list_router, tags=["memory"])
app.include_router(memory_get_search_router, tags=["memory"])
app.include_router(memory_get_semantic_search_router, tags=["memory"])
app.include_router(memory_patch_router, tags=["memory"])
app.include_router(memory_post_router, tags=["memory"])
app.include_router(memory_put_router, tags=["memory"])

register_list_routes(app)

import shared.config
if shared.config.TRACING_ENABLED:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="chromadb")
