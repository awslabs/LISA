"""
Model information routes.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from ....handlers.models import handle_describe_model, handle_describe_models, handle_list_models
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
