"""
Embedding routes.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ....handlers.embeddings import handle_embeddings
from ....utils.resources import EmbeddingsRequest, RestApiResource

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(f"/{RestApiResource.EMBEDDINGS.value}")  # type: ignore
async def embeddings(request: EmbeddingsRequest) -> JSONResponse:
    """Text embeddings."""
    response = await handle_embeddings(request.dict())

    return JSONResponse(content=response, status_code=200)
