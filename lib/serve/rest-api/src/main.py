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
    register_exception_handlers,
    security_middleware,
    validate_input_middleware,
)

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


##############
# MIDDLEWARE #
##############


@app.middleware("http")
async def authenticate(request, call_next):  # type: ignore
    """Authentication middleware.

    Validates tokens and sets user context on request.state.
    Runs after security checks but before request processing.
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
