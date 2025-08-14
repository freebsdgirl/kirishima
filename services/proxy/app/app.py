"""
This module initializes and configures the FastAPI application for the proxy service.
"""

from app.routes.openai import router as openai_router

from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from shared.models.middleware import CacheRequestBodyMiddleware
from fastapi import FastAPI

app = FastAPI()
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])

app.include_router(openai_router, tags=["openai"])

register_list_routes(app)

import json
with open('/app/config/config.json') as f:
    _config = json.load(f)
if _config['tracing_enabled']:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="proxy")