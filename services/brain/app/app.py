"""
This module initializes and configures the FastAPI application for the "brain" service.

It includes the following functionalities:
- Registers routers for various components such as memory, buffer, modes, scheduler, docs, and message handling.
- Supports both single-turn and multi-turn message processing.
- Integrates shared system routes and models.
- Configures tracing if enabled in the shared configuration.

Routers:
- `routes_router`: System-level routes.
- `docs_router`: Documentation-related routes.
- `memory_router`: Memory management routes.
- `buffer_router`: Buffer management routes.
- `modes_router`: Modes configuration routes.
- `scheduler_router`: Task scheduling routes.
- `message_router`: General message handling routes with a prefix `/message`.
- `message_multiturn_router`: Multi-turn message handling routes.
- `message_singleturn_router`: Single-turn message handling routes.
- `models_router`: Model-related routes.

Tracing:
- If tracing is enabled (`shared.config.TRACING_ENABLED`), the application sets up
    tracing using the `setup_tracing` function from the `shared.tracing` module.

Dependencies:
- FastAPI is used to create the application and manage routing.
- Shared configurations and tracing utilities are imported from the `shared` module.
"""

from app.memory import router as memory_router
from app.buffer import router as buffer_router
from app.modes import router as modes_router
from app.scheduler import router as scheduler_router
from app.docs import router as docs_router
from app.message.message import router as message_router
from app.message.multiturn import router as message_multiturn_router
from app.message.singleturn import router as message_singleturn_router
from app.models import router as models_router
from shared.routes import router as routes_router


from fastapi import FastAPI
app = FastAPI()
app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])
app.include_router(memory_router, tags=["memory"])
app.include_router(buffer_router, tags=["buffer"])
app.include_router(modes_router, tags=["modes"])
app.include_router(scheduler_router, tags=["scheduler"])
app.include_router(message_router, prefix="/message", tags=["message"])
app.include_router(message_multiturn_router, tags=["message"])
app.include_router(message_singleturn_router, tags=["message"])
app.include_router(models_router, tags=["models"])


import shared.config
if shared.config.TRACING_ENABLED:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="brain")