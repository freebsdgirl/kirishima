
from app.user.delete import router as user_delete_router
from app.user.get import router as user_get_router
from app.user.summary import router as user_summary_router
from app.user.sync import router as user_sync_router

from app.conversation.delete import router as conversation_delete_router
from app.conversation.get import router as conversation_get_router
from app.conversation.summary import router as conversation_summary_router
from app.conversation.sync import router as conversation_sync_router

from app.setup import init_buffer_db

init_buffer_db()

from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from shared.models.middleware import CacheRequestBodyMiddleware
from fastapi import FastAPI

app = FastAPI()
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])
app.include_router(user_delete_router, tags=["user"])
app.include_router(user_get_router, tags=["user"])
app.include_router(user_summary_router, tags=["user", "summary"])
app.include_router(user_sync_router, tags=["user"])
app.include_router(conversation_delete_router, tags=["conversation"])
app.include_router(conversation_get_router, tags=["conversation"])
app.include_router(conversation_summary_router, tags=["conversation", "summary"])
app.include_router(conversation_sync_router, tags=["conversation"])

register_list_routes(app)

import shared.config
if shared.config.TRACING_ENABLED:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="ledger")
