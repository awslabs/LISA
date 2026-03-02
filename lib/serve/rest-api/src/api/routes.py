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

from api.endpoints.v2 import litellm_passthrough
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE

logger = logging.getLogger(__name__)

router = APIRouter()

# Auth is now handled by auth_middleware in main.py
# Routes can use @require_auth or @require_admin decorators for additional checks

router.include_router(litellm_passthrough.router, prefix="/v2/serve", tags=["litellm_passthrough"])


@router.get("/health")
async def health_check() -> JSONResponse:
    """Health check path.

    This needs to match the path in the config.yaml file.
    """
    try:
        # Basic health verification - check if required environment variables are set
        required_vars = ["AWS_REGION", "LOG_LEVEL"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            content = {"status": "UNHEALTHY", "missing_env_vars": missing_vars}
            return JSONResponse(content=content, status_code=HTTP_503_SERVICE_UNAVAILABLE)

        content = {"status": "OK"}
        return JSONResponse(content=content, status_code=HTTP_200_OK)
    except Exception as e:
        content = {"status": "UNHEALTHY", "error": str(e)}
        return JSONResponse(content=content, status_code=HTTP_503_SERVICE_UNAVAILABLE)
