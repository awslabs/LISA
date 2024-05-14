"""
Model information routes.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..auth import OIDCHTTPBearer
from .endpoints.v1 import embeddings, generation, models

logger = logging.getLogger(__name__)

security = OIDCHTTPBearer()
router = APIRouter()

router.include_router(models.router, prefix="/v1", tags=["models"], dependencies=[Depends(security)])
router.include_router(embeddings.router, prefix="/v1", tags=["embeddings"], dependencies=[Depends(security)])
router.include_router(generation.router, prefix="/v1", tags=["generation"], dependencies=[Depends(security)])


@router.get("/health")  # type: ignore
async def health_check() -> JSONResponse:
    """Health check path.

    This needs to match the path in the config.yaml file.
    """
    content = {"status": "OK"}

    return JSONResponse(content=content, status_code=200)
