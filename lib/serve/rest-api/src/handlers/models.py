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

"""Model route handlers - refactored for testability."""

import logging
from typing import Any, DefaultDict

from fastapi import HTTPException
from services.model_service import ModelService
from utils.cache_manager import get_registered_models_cache
from utils.resources import ModelType

logger = logging.getLogger(__name__)


def _get_model_service() -> ModelService:
    """Factory function to create ModelService with current cache.

    This allows for dependency injection in tests.
    """
    return ModelService(get_registered_models_cache())


async def handle_list_models(
    model_types: list[ModelType], model_service: ModelService | None = None
) -> dict[ModelType, dict[str, list[str]]]:
    """Handle for list_models endpoint.

    Parameters
    ----------
    model_types : List[ModelType]
        Model types to list
    model_service : ModelService | None
        Optional model service for dependency injection (testing)

    Returns
    -------
    Dict[ModelType, Dict[str, List[str]]]
        List of model names by model type and model provider
    """
    service = model_service or _get_model_service()
    return service.list_models(model_types)


async def handle_openai_list_models(model_service: ModelService | None = None) -> dict[str, Any]:
    """Handle for list_models endpoint.

    Parameters
    ----------
    model_service : ModelService | None
        Optional model service for dependency injection (testing)

    Returns
    -------
    Dict[str, Any]
        OpenAI-compatible response object to list Models
    """
    service = model_service or _get_model_service()
    return service.list_models_openai_format()


async def handle_describe_model(
    provider: str, model_name: str, model_service: ModelService | None = None
) -> dict[str, Any]:
    """Handle for describe_model endpoint.

    Parameters
    ----------
    provider : str
        Model provider name
    model_name : str
        Model name
    model_service : ModelService | None
        Optional model service for dependency injection (testing)

    Returns
    -------
    Dict[str, Any]
        Model metadata

    Raises
    ------
    HTTPException
        If model metadata not found
    """
    service = model_service or _get_model_service()
    metadata = service.get_model_metadata(provider, model_name)

    if not metadata:
        error_message = f"Metadata for provider {provider} and model {model_name} not found."
        logger.error(error_message, extra={"event": "handle_describe_model", "status": "ERROR"})
        raise HTTPException(status_code=404, detail=error_message)

    return metadata


async def handle_describe_models(
    model_types: list[ModelType], model_service: ModelService | None = None
) -> DefaultDict[str, DefaultDict[str, dict[str, Any]]]:
    """Handle for describe_models endpoint.

    Parameters
    ----------
    model_types : List[ModelType]
        Model types to list
    model_service : ModelService | None
        Optional model service for dependency injection (testing)

    Returns
    -------
    DefaultDict[str, DefaultDict[str, Dict[str, Any]]]
        Model metadata by model type, model provider, and model name
    """
    service = model_service or _get_model_service()
    return service.describe_models(model_types)
