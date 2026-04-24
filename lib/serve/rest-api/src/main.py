#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License").
#   You may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""REST API."""

import os
import sys
from contextlib import asynccontextmanager

from api.routes import router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from middleware import (
    auth_middleware,
    process_request_middleware,
    rate_limit_middleware,
    register_exception_handlers,
    security_middleware,
    validate_input_middleware,
)
from starlette.types import ASGIApp, Receive, Scope, Send

logger.remove()
logger_level = os.environ.get("LOG_LEVEL", "INFO")
logger.configure(
    extra={
        "request_id": "NO_REQUEST_ID",
        "endpoint": "NO_ENDPOINT",
        "event": "NO_EVENT",
        "status": "NO_STATUS",
    },
    handlers=[
        {
            "sink": sys.stdout,
            "format": (
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <cyan>{extra[request_id]}</cyan> | "
                "<level>{level: <8}</level> | <yellow>{extra[endpoint]}</yellow> | "
                "<blue>{extra[event]}</blue> | <magenta>{extra[status]}</magenta> | {message}"
            ),
            "level": logger_level.upper(),
        }
    ],
)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore
    """REST API lifespan."""
    yield


app = FastAPI(lifespan=lifespan)

# Register exception handlers first (before routes)
register_exception_handlers(app)

app.include_router(router)


# Enable CORS
_cors_origins_env = os.environ.get("CORS_ORIGINS", "*")
_cors_origins = [origin.strip() for origin in _cors_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


##############
# MIDDLEWARE #
##############


@app.middleware("http")
async def rate_limit(request, call_next):  # type: ignore
    """Per-user rate limiting middleware.

    Runs after authentication (user identity is available) to enforce
    per-API-key / per-user request rate limits.
    """
    return await rate_limit_middleware(request, call_next)


@app.middleware("http")
async def authenticate(request, call_next):  # type: ignore
    """Authentication middleware.

    Validates tokens and sets user context on request.state.
    NOTE: Function middleware executes in reverse registration order in FastAPI,
    so this must be declared *after* rate_limit() to run first on requests.
    """
    return await auth_middleware(request, call_next)


@app.middleware("http")
async def validate_input(request, call_next):  # type: ignore
    """Middleware for validating all HTTP request inputs."""
    return await validate_input_middleware(request, call_next)


@app.middleware("http")
async def process_request(request, call_next):  # type: ignore
    """Middleware for processing all HTTP requests (logging)."""
    return await process_request_middleware(request, call_next)


@app.middleware("http")
async def security_check(request, call_next):  # type: ignore
    """Security middleware for input validation.

    This middleware runs FIRST (before request logging) to validate:
    - HTTP method is allowed
    - No null bytes in path, query, or body
    - Request body is valid JSON for POST/PUT/PATCH
    - Request size is within limits (model proxy endpoints are exempt)
    """
    return await security_middleware(request, call_next)


def _parse_asgi_spec_version(spec_version: str) -> tuple[int, ...]:
    """Parse ASGI spec_version like '2.4' into a tuple for comparison."""
    try:
        return tuple(int(p) for p in spec_version.split(".") if p != "")
    except ValueError:
        return (2, 0)


class EnsureAsgiHttpSpec24Middleware:
    """Normalize HTTP scope's ASGI spec_version to >= 2.4.

    Starlette 0.49+ ``StreamingResponse`` runs ``listen_for_disconnect`` in parallel with
    the body iterator only when ``scope['asgi']['spec_version']`` is below 2.4.
    In some deployments this can race with ``BaseHTTPMiddleware`` and raise:

        RuntimeError: Unexpected message received: http.request
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") == "http":
            asgi = scope.setdefault("asgi", {})
            raw = str(asgi.get("spec_version", "2.0"))
            if _parse_asgi_spec_version(raw) < (2, 4):
                asgi["spec_version"] = "2.4"
        await self.app(scope, receive, send)


# Wrap the fully-built FastAPI app (Gunicorn imports ``app`` from this module).
_built_asgi_app: ASGIApp = app
app = EnsureAsgiHttpSpec24Middleware(_built_asgi_app)
