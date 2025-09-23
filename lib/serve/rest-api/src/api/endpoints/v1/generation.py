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

"""Generation routes."""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse

from ....handlers.generation import handle_generate, handle_generate_stream, handle_openai_generate_stream
from ....utils.resources import (
    GenerateRequest,
    GenerateStreamRequest,
    OpenAIChatCompletionsRequest,
    OpenAICompletionsRequest,
    RestApiResource,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(f"/{RestApiResource.GENERATE}")
async def generate(request: GenerateRequest) -> JSONResponse:
    """Text generation."""
    response = await handle_generate(request.dict())

    return JSONResponse(content=response, status_code=200)


@router.post(f"/{RestApiResource.GENERATE_STREAM}")
async def generate_stream(request: GenerateStreamRequest) -> StreamingResponse:
    """Text generation with streaming."""
    return StreamingResponse(
        handle_generate_stream(request.dict()),
        media_type="text/event-stream",
    )


@router.post(f"/{RestApiResource.OPENAI_CHAT_COMPLETIONS}")
async def openai_chat_completion_generate_stream(request: OpenAIChatCompletionsRequest) -> StreamingResponse:
    """Text generation with streaming."""
    return StreamingResponse(
        handle_openai_generate_stream(request.dict()),
        media_type="text/event-stream",
    )


@router.post(f"/{RestApiResource.OPENAI_COMPLETIONS}")
async def openai_completion_generate_stream(request: OpenAICompletionsRequest) -> StreamingResponse:
    """Text generation with streaming."""
    return StreamingResponse(
        handle_openai_generate_stream(request.dict(), is_text_completion=True),
        media_type="text/event-stream",
    )
