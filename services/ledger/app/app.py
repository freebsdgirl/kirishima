from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from shared.models.middleware import CacheRequestBodyMiddleware
from fastapi import FastAPI

app = FastAPI()
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])

register_list_routes(app)

import shared.config
if shared.config.TRACING_ENABLED:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="ledger")
