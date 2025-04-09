"""
This module initializes and configures the FastAPI application for the proxy service.

It includes the following routers:
- `docs_router`: Handles routes related to API documentation.
- `api_router`: Handles general API routes.
- `imessage_router`: Handles routes related to iMessage functionality.

Additionally, it provides a health check endpoint at `/ping` to verify the service status.

Routes:
- `/ping`: Health check endpoint returning `{"status": "ok"}`.

Dependencies:
- FastAPI: A modern, fast (high-performance) web framework for Python.
"""

from app.docs import router as docs_router
from app.api import router as api_router
from app.imessage import router as imessage_router


from fastapi import FastAPI
app = FastAPI()
app.include_router(docs_router)
app.include_router(api_router)
app.include_router(imessage_router)


@app.get("/ping")
def ping():
    return {"status": "ok"}