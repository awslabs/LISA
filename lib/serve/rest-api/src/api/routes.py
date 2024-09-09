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

"""Model information routes."""

import logging
import os

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from ..auth import OIDCHTTPBearer
from .endpoints.v2 import litellm_passthrough

logger = logging.getLogger(__name__)

router = APIRouter()

if os.getenv("USE_AUTH", "true").lower() == "false":
    dependencies = []
    logger.info("Auth disabled")
else:
    security = OIDCHTTPBearer()
    dependencies = [Depends(security)]
    logger.info("Auth enabled")

router.include_router(
    litellm_passthrough.router, prefix="/v2/serve", tags=["litellm_passthrough"], dependencies=dependencies
)


@router.get("/health")  # type: ignore
async def health_check() -> JSONResponse:
    """Health check path.

    This needs to match the path in the config.yaml file.
    """
    content = {"status": "OK"}

    return JSONResponse(content=content, status_code=200)
