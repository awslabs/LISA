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
import time
from contextlib import asynccontextmanager
from typing import Any
from uuid import uuid4

from aiobotocore.session import get_session
from api.routes import router
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from lisa_serve.registry import registry
from loguru import logger
from utils.cache_manager import set_registered_models_cache
from utils.resources import ModelType, RestApiResource

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

    new_models: dict[str, dict[str, Any]] = {
        ModelType.EMBEDDING: {},
        ModelType.TEXTGEN: {},
        RestApiResource.EMBEDDINGS: {},
        RestApiResource.GENERATE: {},
        RestApiResource.GENERATE_STREAM: {},
        "metadata": {},
        "endpointUrls": {},
    }
    try:
        verify_path = os.getenv("SSL_CERT_FILE") or None
        session = get_session()
        async with session.create_client("ssm", region_name=os.environ["AWS_REGION"], verify=verify_path) as client:
            response = await client.get_parameter(Name=os.environ["REGISTERED_MODELS_PS_NAME"])
        registered_models = json.loads(response["Parameter"]["Value"])
        for model in registered_models:
            provider = model["provider"]
            # provider format is `modelHosting.modelType.inferenceContainer`, example: "ecs.textgen.tgi"
            [_, _, inference_container] = provider.split(".")
            model_name = model["modelName"]
            model_type = model["modelType"]

            if inference_container not in ["tgi", "tei", "instructor"]:  # stopgap for supporting new containers for v2
                continue  # not implementing new providers inside the existing cache; cache is on deprecation path

            # Get default model kwargs
            validator = registry.get_assets(provider)["validator"]
            model_kwargs = validator().dict()

            # Get model endpoint URL
            model_key = f"{provider}.{model_name}"
            new_models["endpointUrls"][model_key] = model["endpointUrl"]

            # Get other model metadata to expose to endpoints
            new_models["metadata"][model_key] = {
                "provider": provider,
                "modelName": model_name,
                "modelType": model_type,
                "modelKwargs": model_kwargs,
            }
            if "streaming" in model:
                new_models["metadata"][model_key]["streaming"] = model["streaming"]

            # Make list of registered accessible either by ModelType and by RestApiResource
            if model_type == ModelType.EMBEDDING:
                new_models[RestApiResource.EMBEDDINGS].setdefault(provider, []).append(model_name)
                new_models[ModelType.EMBEDDING].setdefault(provider, []).append(model_name)
            elif model_type == ModelType.TEXTGEN:
                new_models[RestApiResource.GENERATE].setdefault(provider, []).append(model_name)
                new_models[ModelType.TEXTGEN].setdefault(provider, []).append(model_name)
                if model["streaming"]:
                    new_models[RestApiResource.GENERATE_STREAM].setdefault(provider, []).append(model_name)

        # Update the global cache
        set_registered_models_cache(new_models)
    except Exception:
        task_logger.exception("An unknown error occurred", status="ERROR")

    yield
    task_logger.debug("Finished API Lifespan task", status="FINISH")


app = FastAPI(lifespan=lifespan)
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
async def process_request(request: Request, call_next: Any) -> Any:
    """Middleware for processing all HTTP requests."""
    event = "process_request"
    request_id = str(uuid4())  # Unique ID for this request
    tic = time.time()

    with logger.contextualize(request_id=request_id, endpoint=request.url.path):
        try:
            task_logger = logger.bind(event=event)
            task_logger.debug("Start task", status="START")

            # Attempt to call the next request handler
            response = await call_next(request)

            # If response is successful, log the finish status
            duration = time.time() - tic
            task_logger.debug(f"Finish task (took {duration:.2f} seconds)", status="FINISH")

        except Exception as e:
            # In case of an exception, log the error and prepare a generic response
            duration = time.time() - tic
            task_logger.exception(
                f"Error occurred during processing: {e} (took {duration:.2f} seconds)",
                status="ERROR",
            )
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
            )

        # Add the unique request ID to the response headers
        if response is not None and isinstance(response, Response):
            response.headers["X-Request-ID"] = request_id

    return response
