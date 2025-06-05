
from app.user.delete import router as user_delete_router
from app.user.get import router as user_get_router
from app.user.sync import router as user_sync_router

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
app.include_router(user_sync_router, tags=["user"])

register_list_routes(app)

import json
with open('/app/shared/config.json') as f:
    _config = json.load(f)
if _config['tracing_enabled']:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="ledger")
