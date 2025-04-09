"""
This module initializes and configures the FastAPI application for the brain system.

It imports and includes various routers from different submodules of the `brain` package,
allowing the application to handle routes related to memory, buffer, status, job scheduling,
documentation, and messaging.

Modules and Components:
- `brain.config`: Configuration settings for the brain system.
- `brain.memory.router`: Router for memory-related endpoints.
- `brain.buffer.router`: Router for buffer-related endpoints.
- `brain.status.router`: Router for status-related endpoints.
- `brain.jobscheduler.router`: Router for job scheduling endpoints.
- `brain.docs.router`: Router for documentation-related endpoints.
- `brain.message.router`: Router for messaging-related endpoints.
- `log_config.get_logger`: Utility function to configure and retrieve a logger.

Attributes:
- `logger`: Logger instance for logging messages in this module.
- `app`: FastAPI application instance with all the routers included.

Routers Included:
- `memory_router`: Handles memory-related API routes.
- `buffer_router`: Handles buffer-related API routes.
- `status_router`: Handles status-related API routes.
- `scheduler_router`: Handles job scheduling API routes.
- `docs_router`: Handles documentation-related API routes.
- `message_router`: Handles messaging-related API routes.
"""
from app.memory import router as memory_router
from app.buffer import router as buffer_router
from app.status import router as status_router
from app.scheduler import router as scheduler_router
from app.docs import router as docs_router
from app.message import router as message_router

from fastapi import FastAPI
app = FastAPI()

app.include_router(memory_router)
app.include_router(buffer_router)
app.include_router(status_router)
app.include_router(scheduler_router)
app.include_router(docs_router)
app.include_router(message_router, prefix="/message", tags=["message"])


@app.get("/ping")
def ping():
    return {"status": "ok"}
