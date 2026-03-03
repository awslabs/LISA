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
from starlette.middleware.base import BaseHTTPMiddleware

from middleware import register_exception_handlers
from middleware.combined_http import combined_http_dispatch
from middleware.streaming_safe import StreamingSafeMiddleware

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

# Consume request body at ASGI layer and provide a receive that returns body once then
# only http.disconnect, so StreamingResponse never sees a second http.request (avoids
# RuntimeError when BaseHTTPMiddleware or similar is in the chain). Add last so it is
# outermost and receives the server's receive first.
app.add_middleware(StreamingSafeMiddleware)

# Single BaseHTTPMiddleware that chains security, process_request, validate_input, and
# auth (one layer instead of four) to avoid "No response returned" with StreamingResponse.
app.add_middleware(BaseHTTPMiddleware, dispatch=combined_http_dispatch)
