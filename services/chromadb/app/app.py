"""
This module initializes and configures a FastAPI application for the Chroma embedding service.

The application provides endpoints for managing text embeddings and integrates routers for 
memory management, text summarization, and buffer operations. Each router is registered 
with a specific URL prefix and tag to organize the API documentation.

Modules:
    chroma.memory.router: Contains endpoints for memory-related operations.
    chroma.summarize.router: Contains endpoints for text summarization.
    chroma.buffer.router: Contains endpoints for buffer-related operations.
    log_config: Provides logging configuration for the application.

    app (FastAPI): The main FastAPI application instance that handles HTTP requests.
"""

from app.memory import router as memory_router
from app.summarize import router as summarize_router
from app.buffer import router as buffer_router
from app.docs import router as docs_router


"""
Initialize the FastAPI application for the Chroma embedding service.

This application provides endpoints for creating and managing text embeddings,
with integration for memory and summarization routers.

Attributes:
    app (FastAPI): The main FastAPI application instance for handling HTTP requests.
"""
from fastapi import FastAPI
app = FastAPI()


"""
Include additional routers for memory, summarization, and buffer operations in the FastAPI application.

These routers extend the application's functionality by adding specialized endpoints
for memory management, text summarization, and buffer-related operations.

Routers are registered with specific URL prefixes and tags for organized API documentation.
"""
app.include_router(memory_router, prefix="/memory", tags=["memory"])
app.include_router(summarize_router, prefix="/summary", tags=["summary"])
app.include_router(buffer_router, prefix="/buffer", tags=["buffer"])
app.include_router(docs_router, prefix="/docs", tags=["docs"])


@app.get("/ping")
def ping():
    return {"status": "ok"}