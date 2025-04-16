
from shared.routes import router as routes_router

from fastapi import FastAPI
app = FastAPI()
app.include_router(routes_router, tags=["system"])


import shared.config
if shared.config.TRACING_ENABLED:
    from shared.tracing import setup_tracing
    setup_tracing(app, service_name="intents")
