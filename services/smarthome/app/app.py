from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from shared.log_config import get_logger
logger = get_logger(f"smarthome.{__name__}")

from shared.models.middleware import CacheRequestBodyMiddleware
from fastapi import FastAPI

from app.list_devices import router as list_devices_router

app = FastAPI()
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])
app.include_router(list_devices_router, tags=["smarthome"])

register_list_routes(app)

import json
with open('/app/shared/config.json') as f:
    _config = json.load(f)
if _config['tracing_enabled']:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="smarthome")