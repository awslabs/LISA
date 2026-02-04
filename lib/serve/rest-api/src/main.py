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
import json
import os
import sys
from contextlib import asynccontextmanager

import boto3
from api.routes import router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from lisa_serve.registry import registry
from loguru import logger
from middleware import process_request_middleware, register_exception_handlers, security_middleware, validate_input_middleware
from services.model_registration import ModelRegistrationService
from utils.cache_manager import set_registered_models_cache

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
    """REST API start and update task."""
    event = "start_and_update_task"
    task_logger = logger.bind(event=event)
    task_logger.debug("Start task", status="START")

    # Create model registration service
    registration_service = ModelRegistrationService(registry)

    try:
        verify_path = os.getenv("SSL_CERT_FILE") or None
        # Use synchronous boto3 client - this runs once at startup so async isn't needed
        # This avoids aiobotocore dependency which has version conflicts with litellm's boto3
        ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], verify=verify_path)
        response = ssm_client.get_parameter(Name=os.environ["REGISTERED_MODELS_PS_NAME"])

        registered_models = json.loads(response["Parameter"]["Value"])

        # Register all models using the service
        new_models = registration_service.register_models(registered_models)

        # Update the global cache
        set_registered_models_cache(new_models)
    except Exception:
        task_logger.exception("An unknown error occurred", status="ERROR")

    yield
    task_logger.debug("Finished API Lifespan task", status="FINISH")


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
