"""
Generation route handlers.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""
import json
import logging
from typing import Any, AsyncGenerator, Dict

from ..utils.request_utils import handle_stream_exceptions, validate_and_prepare_llm_request
from ..utils.resources import RestApiResource

logger = logging.getLogger(__name__)


async def handle_generate(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle for generate endpoint."""
    model, model_kwargs, text = await validate_and_prepare_llm_request(request_data, RestApiResource.GENERATE)
    response = await model.generate(text=text, model_kwargs=model_kwargs)

    return response.dict()  # type: ignore


@handle_stream_exceptions  # type: ignore
async def handle_generate_stream(request_data: Dict[str, Any]) -> AsyncGenerator[str, None]:
    """Handle for generate_stream endpoint."""
    model, model_kwargs, text = await validate_and_prepare_llm_request(request_data, RestApiResource.GENERATE_STREAM)
    async for response in model.generate_stream(text=text, model_kwargs=model_kwargs):
        yield f"data:{json.dumps(response.dict(exclude_none=True))}\n\n"
