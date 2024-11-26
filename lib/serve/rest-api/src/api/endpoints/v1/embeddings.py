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

"""Embedding routes."""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ....handlers.embeddings import handle_embeddings
from ....utils.resources import EmbeddingsRequest, RestApiResource

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(f"/{RestApiResource.EMBEDDINGS.value}")
async def embeddings(request: EmbeddingsRequest) -> JSONResponse:
    """Text embeddings."""
    response = await handle_embeddings(request.dict())

    return JSONResponse(content=response, status_code=200)
