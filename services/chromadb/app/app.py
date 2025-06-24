"""
Main FastAPI application setup for the ChromaDB service.

This module initializes the FastAPI app, adds middleware, and includes routers for various
functionalities such as embedding, memory operations (delete, get, search, patch, post, put),
documentation, and system routes. It also conditionally sets up tracing if enabled in the configuration.

Routers included:
- Embedding operations
- Memory operations (delete, get by ID, list, search, semantic search, patch, post, put)
- Documentation exporter
- System routes

Middleware:
- CacheRequestBodyMiddleware: Caches the request body for downstream processing.

Conditional Features:
- Tracing: If enabled in the configuration, tracing is set up for the service.

Functions:
- register_list_routes: Registers additional list routes to the FastAPI app.
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

from app.summary.delete import router as summary_delete_router
from app.summary.get import router as summary_get_router
from app.summary.post import router as summary_post_router

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

app.include_router(summary_delete_router, tags=["summary"])
app.include_router(summary_get_router, tags=["summary"])
app.include_router(summary_post_router, tags=["summary"])

register_list_routes(app)

import json
with open('/app/config/config.json') as f:
    _config = json.load(f)
if _config['tracing_enabled']:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="chromadb")
