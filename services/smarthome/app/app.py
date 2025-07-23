from shared.docs_exporter import router as docs_router
from shared.routes import router as routes_router, register_list_routes

from shared.log_config import get_logger
logger = get_logger(f"smarthome.{__name__}")

from shared.models.middleware import CacheRequestBodyMiddleware
from fastapi import FastAPI

from app.routes.area import router as area_router
from app.routes.device import router as device_router
from app.routes.entity import router as entity_router
from app.routes.json import router as json_router
from app.routes.request import router as request_router


app = FastAPI()
app.add_middleware(CacheRequestBodyMiddleware)

app.include_router(routes_router, tags=["system"])
app.include_router(docs_router, tags=["docs"])

app.include_router(area_router, prefix="/area", tags=["area"])
app.include_router(device_router, prefix="/device", tags=["device"])
app.include_router(entity_router, prefix="/entity", tags=["entity"])
app.include_router(json_router, tags=["json"])
app.include_router(request_router, tags=["request"])


register_list_routes(app)

import json
with open('/app/config/config.json') as f:
    _config = json.load(f)
if _config['tracing_enabled']:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="smarthome")