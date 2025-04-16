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
    app = FastAPI()
    app.middleware("http")(CacheRequestBodyMiddleware())

    from fastapi import FastAPI
    from shared.middleware import CacheRequestBodyMiddleware
"""

from fastapi import Request


class CacheRequestBodyMiddleware:
    """
    A middleware class that caches the request body for later access.
    
    This middleware intercepts incoming HTTP requests, reads the raw request body,
    and attaches it to the request's state for subsequent use in the request lifecycle.
    
    Args:
        request (Request): The incoming HTTP request.
        call_next (Callable): A function to call the next middleware or request handler.
    
    Returns:
        Response: The response from the next middleware or request handler.
    """
    async def __call__(self, request: Request, call_next):
        body = await request.body()
        # Attach the raw body to the request state for later use
        request.state.raw_body = body
        response = await call_next(request)
        return response