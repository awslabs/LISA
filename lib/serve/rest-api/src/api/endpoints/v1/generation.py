"""
Generation routes.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from ....handlers.generation import handle_generate, handle_generate_stream
from ....utils.resources import GenerateRequest, GenerateStreamRequest, RestApiResource

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(f"/{RestApiResource.GENERATE.value}")  # type: ignore
async def generate(request: GenerateRequest) -> JSONResponse:
    """Text generation."""
    response = await handle_generate(request.dict())

    return JSONResponse(content=response, status_code=200)


@router.post(f"/{RestApiResource.GENERATE_STREAM.value}")  # type: ignore
async def generate_stream(request: GenerateStreamRequest) -> StreamingResponse:
    """Text generation with streaming."""
    return StreamingResponse(
        handle_generate_stream(request.dict()),
        media_type="text/event-stream",
    )
