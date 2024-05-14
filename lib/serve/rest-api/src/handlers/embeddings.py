"""
Embedding route handlers.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""
import logging
from typing import Any, Dict

from ..utils.request_utils import validate_and_prepare_llm_request
from ..utils.resources import RestApiResource

logger = logging.getLogger(__name__)


async def handle_embeddings(request_data: Dict[str, Any]) -> Dict[str, Any]:
    """Handle for embeddings endpoint."""
    model, model_kwargs, text = await validate_and_prepare_llm_request(request_data, RestApiResource.EMBEDDINGS)
    response = await model.embed_query(text=text, model_kwargs=model_kwargs)

    return response.dict()  # type: ignore
