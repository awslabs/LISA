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

"""Model route handlers."""

import logging
import time
from collections import defaultdict
from typing import Any, DefaultDict, Dict, List

from fastapi import HTTPException

from ..utils.cache_manager import get_registered_models_cache
from ..utils.resources import ModelType

logger = logging.getLogger(__name__)


async def handle_list_models(model_types: List[ModelType]) -> Dict[ModelType, Dict[str, List[str]]]:
    """Handle for list_models endpoint.

    Parameters
    ----------
    model_types : List[ModelType]
        Model types to list.

    registered_models_cache : Dict[str, Dict[str, Any]]
        Registered models cache.

    Returns
    -------
    Dict[ModelType, Dict[str, List[str]]]
        List of model names by model type and model provider.
    """
    registered_models_cache = get_registered_models_cache()
    response = {model_type: registered_models_cache[model_type] for model_type in model_types}

    return response


async def handle_openai_list_models() -> Dict[str, Any]:
    """Handle for list_models endpoint.

    Returns
    -------
    Dict[str, Union[str, Any]
        OpenAI-compatible response object to list Models. This only returns Text Generation models.
    """
    registered_models_cache = get_registered_models_cache()

    model_payload: List[Dict[str, Any]] = []
    for provider, models in registered_models_cache[ModelType.TEXTGEN].items():
        model_payload.extend(
            {"id": f"{model} ({provider})", "object": "model", "created": int(time.time()), "owned_by": "LISA"}
            for model in models
        )

    response = {"data": model_payload, "object": "list"}
    return response


async def handle_describe_model(provider: str, model_name: str) -> Dict[str, Any]:
    """Handle for describe_model endpoint.

    Parameters
    ----------
    provider : str
        Model provider name.

    model_name : str
        Model name.

    Returns
    -------
    Dict[str, Any]
        Model metadata.
    """
    model_key = f"{provider}.{model_name}"
    registered_models_cache = get_registered_models_cache()
    metadata = registered_models_cache["metadata"].get(model_key)
    if not metadata:
        error_message = f"Metadata for provider {provider} and model {model_name} not found."
        logger.error(error_message, extra={"event": "handle_describe_model", "status": "ERROR"})
        raise HTTPException(status_code=404, detail=error_message)

    return metadata  # type: ignore


async def handle_describe_models(model_types: List[ModelType]) -> DefaultDict[str, DefaultDict[str, Dict[str, Any]]]:
    """Handle for describe_models endpoint.

    Parameters
    ----------
    model_types : List[ModelType]
        Model types to list.

    Returns
    -------
    DefaultDict[str, DefaultDict[str, Dict[str, Any]]]
        Model metadata by model type, model provider, and model name.
    """
    registered_models = await handle_list_models(model_types)
    registered_models_cache = get_registered_models_cache()
    response: DefaultDict[str, DefaultDict[str, Dict[str, Any]]] = defaultdict(lambda: defaultdict(dict))

    for model_type, providers in registered_models.items():
        response[model_type] = {}  # type: ignore
        providers = providers or {}
        for provider, model_names in providers.items():
            response[model_type][provider] = [
                registered_models_cache["metadata"][f"{provider}.{model_name}"] for model_name in model_names
            ]  # type: ignore

    return response
