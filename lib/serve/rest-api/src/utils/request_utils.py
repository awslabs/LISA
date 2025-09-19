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

"""Utility functions for handling request data."""
import json
import os
import sys
import traceback
from typing import Any, AsyncGenerator, Callable, Dict, Tuple

from loguru import logger

from ..lisa_serve.registry import registry
from .cache_manager import cache_model_assets, get_model_assets, get_registered_models_cache
from .resources import RestApiResource

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


async def validate_model(request_data: Dict[str, Any], resource: RestApiResource) -> None:
    """Validate that the selected model is registered and supported for the specified resource.

    Parameters
    ----------
    request_data : Dict[str, Any]
        Request data.

    resource : RestApiResource
        REST API resource.

    Raises
    ------
    Exception
        If the selected model is not registered or not supported for the specified resource.

    Returns
    -------
    None
        None.

    """
    event = "validate_model"

    provider = request_data["provider"]
    model_name = request_data["modelName"]

    registered_models_cache = get_registered_models_cache()
    supported_models = registered_models_cache[resource][provider]
    if model_name not in supported_models:
        # Sanitize inputs for logging to prevent log injection
        safe_model_name = str(model_name).replace("\n", "").replace("\r", "")
        safe_resource = str(resource).replace("\n", "").replace("\r", "")
        safe_supported = str(supported_models).replace("\n", "").replace("\r", "")

        message = (
            f"Provider does not support model {safe_model_name} for endpoint "
            f"/{safe_resource}, expected one of: {safe_supported}"
        )
        logger.error(message, extra={"event": event, "status": "ERROR"})
        raise ValueError(message)


async def get_model_and_validator(request_data: Dict[str, Any]) -> Tuple[Any, Any]:
    """Get model and model kwargs validator.

    Parameters
    ----------
    request_data : Dict[str, Any]
        Request data.

    Returns
    -------
    Tuple
        The model and model kwargs validator.
    """
    provider = request_data["provider"]
    model_name = request_data["modelName"]
    model_key = f"{provider}.{model_name}"

    # Try to get model and validator from the cache
    model_assets = get_model_assets(model_key)
    if not model_assets:
        # If not cached, retrieve model assets from registry
        registry_assets = registry.get_assets(provider)
        adapter = registry_assets["adapter"]
        validator = registry_assets["validator"]

        # Retrieve model endpoint URL
        registered_models_cache = get_registered_models_cache()
        try:
            endpoint_url = registered_models_cache["endpointUrls"][model_key]
        except KeyError:
            raise KeyError(f"Model endpoint URL not found for {model_key}")

        # Instantiate the model
        model = adapter(model_name=model_name, endpoint_url=endpoint_url)

        # Store model and validator in the cache
        model_assets = (model, validator)
        cache_model_assets(model_key, model_assets)

    return model_assets


async def validate_and_prepare_llm_request(
    request_data: Dict[str, Any], resource: RestApiResource
) -> Tuple[Any, Any, str]:
    """Validate and prepare data for LLM (Language Model) requests.

    Parameters
    ----------
    request_data : Dict[str, Any]
        Request data.

    resource : RestApiResource
        REST API resource.

    Returns
    -------
    Tuple
        The model, prepared model kwargs, and text for processing.
    """
    event = "validate_and_prepare_llm_request"
    task_logger = logger.bind(event=event)
    task_logger.debug("Start task", status="START")

    # Validate the requested model is registered
    await validate_model(request_data, resource)

    # Instantiate the model and get the model kwargs validator
    model, validator = await get_model_and_validator(request_data)

    # Verify model kwargs
    model_kwargs = validator(**request_data["modelKwargs"])

    task_logger.debug("Finish task", status="FINISH")

    text = request_data.get("text")
    if text is None:
        raise ValueError("Missing required field: text")

    return model, model_kwargs.dict(), text


def handle_stream_exceptions(
    func: Callable[..., AsyncGenerator[str, None]]
) -> Callable[..., AsyncGenerator[str, None]]:
    """Decorate a streaming function to handle exceptions gracefully.

    This decorator catches any exceptions raised during the execution of a streaming function
    and yields a formatted error message as a string in the stream. The error message contains
    the type of the exception, the error message, and the traceback.

    Parameters
    ----------
    func : Callable[..., AsyncGenerator[str, None]]
        The streaming function to wrap. This function is expected to be an asynchronous generator
        yielding strings.

    Returns
    -------
    wrapper : Callable[..., AsyncGenerator[str, None]]
        The wrapped function, which handles exceptions by yielding them as formatted error messages
        in the stream.

    Yields
    ------
    str
        The items yielded by the original function, or a JSON-formatted error message in case of an exception.
    """

    async def wrapper(*args: Any, **kwargs: Any) -> AsyncGenerator[str, None]:
        try:
            async for item in func(*args, **kwargs):
                yield item
        except Exception as e:
            error_message = {
                "error": {
                    "type": type(e).__name__,
                    "message": str(e),
                    "trace": traceback.format_exc(),
                }
            }
            logger.exception(
                error_message["error"]["message"],
                extra={"event": "handle_stream_exceptions", "status": "ERROR"},
            )
            yield f"data:{json.dumps({'event': 'error', 'data': error_message})}\n\n"

    return wrapper
