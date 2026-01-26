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

"""Generation route handlers - refactored for testability."""
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from services.text_processing import (
    map_openai_params_to_lisa,
    parse_model_provider_from_string,
    render_context_from_messages,
)
from utils.request_utils import (
    handle_stream_exceptions,
    RegistryProtocol,
    validate_and_prepare_llm_request,
)
from utils.resources import RestApiResource

logger = logging.getLogger(__name__)


async def handle_generate(request_data: dict[str, Any], registry: RegistryProtocol | None = None) -> dict[str, Any]:
    """Handle for generate endpoint.

    Parameters
    ----------
    request_data : dict[str, Any]
        Request data
    registry : RegistryProtocol | None
        Optional registry for dependency injection (testing)

    Returns
    -------
    dict[str, Any]
        Generation response
    """
    model, model_kwargs, text = await validate_and_prepare_llm_request(request_data, RestApiResource.GENERATE, registry)
    try:
        response = await model.generate(text=text, model_kwargs=model_kwargs)
        return response.dict()  # type: ignore
    except Exception as e:
        logger.error(f"Model generation failed: {e}")
        raise


@handle_stream_exceptions
async def handle_generate_stream(
    request_data: dict[str, Any], registry: RegistryProtocol | None = None
) -> AsyncGenerator[str]:
    """Handle for generate_stream endpoint.

    Parameters
    ----------
    request_data : dict[str, Any]
        Request data
    registry : RegistryProtocol | None
        Optional registry for dependency injection (testing)

    Yields
    ------
    str
        Streaming response chunks
    """
    model, model_kwargs, text = await validate_and_prepare_llm_request(
        request_data, RestApiResource.GENERATE_STREAM, registry
    )
    async for response in model.generate_stream(text=text, model_kwargs=model_kwargs):
        yield f"data:{json.dumps(response.dict(exclude_none=True))}\n\n"


@handle_stream_exceptions
async def handle_openai_generate_stream(
    request_data: dict[str, Any], is_text_completion: bool = False, registry: RegistryProtocol | None = None
) -> AsyncGenerator[str]:
    """Handle for openai_generate_stream endpoint.

    Parameters
    ----------
    request_data : dict[str, Any]
        Request data
    is_text_completion : bool
        Whether this is a text completion request
    registry : RegistryProtocol | None
        Optional registry for dependency injection (testing)

    Yields
    ------
    str
        Streaming response chunks
    """
    # Map OpenAI parameters to LISA parameters
    mapped_kwargs = map_openai_params_to_lisa(request_data)

    # Extract text based on completion type
    if is_text_completion:
        text = request_data["prompt"]  # text is already a string
    else:
        text = render_context_from_messages(request_data["messages"])  # convert list to string

    # Parse model and provider
    model_name, provider = parse_model_provider_from_string(request_data["model"])

    # Build LISA request
    lisa_request_data = {
        "modelName": model_name,
        "provider": provider,
        "text": text,
        "streaming": request_data.get("stream", False),
        "modelKwargs": mapped_kwargs,
    }

    model, model_kwargs, text = await validate_and_prepare_llm_request(
        lisa_request_data, RestApiResource.GENERATE_STREAM, registry
    )

    async for response in model.openai_generate_stream(
        text=text, model_kwargs=model_kwargs, is_text_completion=is_text_completion
    ):
        yield f"data:{json.dumps(response.dict(exclude_none=True))}\n\n"

    if is_text_completion:
        yield "data: [DONE]\n\n"


# Keep backward compatibility - these are now just aliases to the service functions
render_context = render_context_from_messages
parse_model_provider_names = parse_model_provider_from_string
