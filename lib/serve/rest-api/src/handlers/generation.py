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

"""Generation route handlers."""
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

from ..utils.request_utils import handle_stream_exceptions, validate_and_prepare_llm_request
from ..utils.resources import RestApiResource

logger = logging.getLogger(__name__)


async def handle_generate(request_data: dict[str, Any]) -> dict[str, Any]:
    """Handle for generate endpoint."""
    model, model_kwargs, text = await validate_and_prepare_llm_request(request_data, RestApiResource.GENERATE)
    try:
        response = await model.generate(text=text, model_kwargs=model_kwargs)
        return response.dict()  # type: ignore
    except Exception as e:
        logger.error(f"Model generation failed: {e}")
        raise


@handle_stream_exceptions
async def handle_generate_stream(request_data: dict[str, Any]) -> AsyncGenerator[str]:
    """Handle for generate_stream endpoint."""
    model, model_kwargs, text = await validate_and_prepare_llm_request(request_data, RestApiResource.GENERATE_STREAM)
    async for response in model.generate_stream(text=text, model_kwargs=model_kwargs):
        yield f"data:{json.dumps(response.dict(exclude_none=True))}\n\n"


def render_context(messages_list: list[dict[str, str]]) -> str:
    """Provide context string for LLM from previous messages."""
    out_str = "\n\n".join([message["content"] for message in messages_list])
    return out_str


def parse_model_provider_names(model_string: str) -> tuple[str, str]:
    """Parse out the model name and its provider name from the combined name of the two.

    Format is assumed to be `${model_name} (${provider_name})` and neither of the model_name or provider_name have
    a space in them. Requests using the OpenAI text generation APIs will require that model names follow this format.
    """
    model_parts = model_string.split()
    model_name = model_parts[0].strip()
    provider = model_parts[1].replace("(", "").replace(")", "").strip()
    return model_name, provider


@handle_stream_exceptions
async def handle_openai_generate_stream(
    request_data: dict[str, Any], is_text_completion: bool = False
) -> AsyncGenerator[str]:
    """Handle for openai_generate_stream endpoint."""
    # map OpenAI API settings (keys) with corresponding TGI model settings (values). Any unsupported options ignored.
    request_mapping = {
        "echo": "return_full_text",
        "frequency_penalty": "repetition_penalty",
        "max_tokens": "max_new_tokens",
        "seed": "seed",
        "stop": "stop_sequences",
        "temperature": "temperature",
        "top_p": "top_p",
    }
    mapped_kwargs = {
        request_mapping[k]: request_data[k] for k in request_mapping if k in request_data and request_data[k]
    }

    if is_text_completion:
        text = request_data["prompt"]  # text is already a string
    else:
        text = render_context(request_data["messages"])  # text must be converted from a list to a string
    model_name, provider = parse_model_provider_names(request_data["model"])
    lisa_request_data = {
        "modelName": model_name,
        "provider": provider,
        "text": text,
        "streaming": request_data.get("stream", False),
        "modelKwargs": mapped_kwargs,
    }
    model, model_kwargs, text = await validate_and_prepare_llm_request(
        lisa_request_data, RestApiResource.GENERATE_STREAM
    )
    async for response in model.openai_generate_stream(
        text=text, model_kwargs=model_kwargs, is_text_completion=is_text_completion
    ):
        yield f"data:{json.dumps(response.dict(exclude_none=True))}\n\n"
    if is_text_completion:
        yield "data: [DONE]\n\n"
