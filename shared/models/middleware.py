"""
This module defines a middleware class for caching the request body in FastAPI.
Classes:
    CacheRequestBodyMiddleware: Middleware to cache the raw request body and attach it 
    to the request's state for later use.
Usage:
    Add the `CacheRequestBodyMiddleware` to your FastAPI application to enable caching 
    of the request body. This can be useful for scenarios where the request body needs 
    to be accessed multiple times during the request lifecycle.
Example:
    from fastapi import FastAPI
    from shared.models.middleware import CacheRequestBodyMiddleware

    app = FastAPI()
    app.add_middleware(CacheRequestBodyMiddleware)
    app.include_router(router)
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class CacheRequestBodyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Read and cache the entire request body
        body = await request.body()
        request.state.raw_body = body
        response = await call_next(request)
        return response