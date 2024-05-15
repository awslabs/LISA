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

"""Model information routes."""

import logging
from typing import List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from ....handlers.models import (
    handle_describe_model,
    handle_describe_models,
    handle_list_models,
    handle_openai_list_models,
)
from ....utils.resources import ModelType, RestApiResource

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(f"/{RestApiResource.DESCRIBE_MODEL.value}")  # type: ignore
async def describe_model(
    provider: str = Query(
        None,
        description="Model provider name.",
        alias="provider",
    ),
    model_name: str = Query(
        None,
        description="Name of model.",
        alias="modelName",
    ),
) -> JSONResponse:
    """Describe model by provider and model name."""
    response = await handle_describe_model(provider, model_name)

    return JSONResponse(content=response, status_code=200)


@router.get(f"/{RestApiResource.DESCRIBE_MODELS.value}")  # type: ignore
async def describe_models(
    model_types: Optional[List[ModelType]] = Query(
        None,
        description="The types of models to list. If not provided, all types will be listed.",
        alias="modelTypes",
    ),
) -> JSONResponse:
    """Describe models by model type."""
    if model_types is None:
        model_types = list(ModelType)

    response = await handle_describe_models(model_types)

    return JSONResponse(content=response, status_code=200)


@router.get(f"/{RestApiResource.LIST_MODELS.value}")  # type: ignore
async def list_models(
    model_types: Optional[List[ModelType]] = Query(
        None,
        description="The types of models to list. If not provided, all types will be listed.",
        alias="modelTypes",
    ),
) -> JSONResponse:
    """List models by model type."""
    if model_types is None:
        model_types = list(ModelType)

    response = await handle_list_models(model_types)

    return JSONResponse(content=response, status_code=200)


@router.get(f"/{RestApiResource.OPENAI_LIST_MODELS.value}")  # type: ignore
async def openai_list_models() -> JSONResponse:
    """List models for OpenAI Compatibility. Only returns TEXTGEN models."""
    response = await handle_openai_list_models()
    return JSONResponse(content=response, status_code=200)
