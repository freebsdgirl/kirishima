"""
This module initializes and configures the FastAPI application for the "brain" service.

It includes the following functionalities:
- Registers routers for various components such as memory, buffer, modes, scheduler, docs, message handling, models, and embeddings.
- Sets up system-level routes and documentation routes.
- Configures message-related routes with specific prefixes and tags.
- Optionally enables tracing if the `TRACING_ENABLED` configuration is set to `True`.

Modules and Routers:
- `memory_router`: Handles memory-related operations.
- `buffer_router`: Manages buffer-related functionalities.
- `modes_router`: Provides endpoints for mode configurations.
- `scheduler_router`: Manages scheduling tasks.
- `docs_router`: Serves API documentation.
- `message_router`: Handles general message-related operations.
- `message_multiturn_router`: Manages multi-turn message interactions.
- `message_singleturn_router`: Handles single-turn message interactions.
- `models_router`: Provides endpoints for model-related operations.
- `embedding_router`: Manages embedding-related functionalities.
- `routes_router`: Defines shared system-level routes.

Tracing:
- If tracing is enabled via the `TRACING_ENABLED` configuration, the `setup_tracing` function is invoked to integrate tracing capabilities with the application.
"""

from app.modes import router as modes_router
from app.scheduler import router as scheduler_router
from app.memory.functions import router as memory_functions_router
from app.memory.list import router as memory_list_router
from app.message.multiturn import router as message_multiturn_router
from app.message.singleturn import router as message_singleturn_router
from app.models import router as models_router
from app.embedding import router as embedding_router
from app.discord.dm import router as discord_dm_router

from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes


from shared.models.middleware import CacheRequestBodyMiddleware
from fastapi import FastAPI
app = FastAPI()
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])
app.include_router(modes_router, tags=["modes"])
app.include_router(scheduler_router, tags=["scheduler"])
app.include_router(memory_functions_router, tags=["memory"])
app.include_router(memory_list_router, tags=["memory"])
app.include_router(message_multiturn_router, tags=["message"])
app.include_router(message_singleturn_router, tags=["message"])
app.include_router(models_router, tags=["models"])
app.include_router(embedding_router, tags=["embedding"])
app.include_router(discord_dm_router, tags=["discord"])

register_list_routes(app)

import shared.config
if shared.config.TRACING_ENABLED:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="brain")