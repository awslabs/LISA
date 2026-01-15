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

"""APIGW endpoints for managing API tokens."""
import logging
import os
from typing import Annotated, Union

import boto3
from fastapi import HTTPException, Path, Request
from fastapi.responses import JSONResponse
from mangum import Mangum
from utilities.auth import get_user_context, is_api_user
from utilities.common_functions import retry_config
from utilities.fastapi_factory import create_fastapi_app

from .domain_objects import (
    CreateTokenAdminRequest,
    CreateTokenResponse,
    CreateTokenUserRequest,
    DeleteTokenResponse,
    ListTokensResponse,
    TokenInfo,
)
from .exception import ForbiddenError, TokenAlreadyExistsError, TokenNotFoundError, UnauthorizedError
from .handler import (
    CreateTokenAdminHandler,
    CreateTokenUserHandler,
    DeleteTokenHandler,
    GetTokenHandler,
    ListTokensHandler,
)

logger = logging.getLogger(__name__)

app = create_fastapi_app()

# Initialize boto3 resources
dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
token_table = dynamodb.Table(os.environ["TOKEN_TABLE_NAME"])


@app.exception_handler(TokenNotFoundError)
async def token_not_found_handler(request: Request, exc: TokenNotFoundError) -> JSONResponse:
    """Handle exception when token cannot be found and translate to a 404 error."""
    return JSONResponse(status_code=404, content={"message": str(exc)})


@app.exception_handler(TokenAlreadyExistsError)
@app.exception_handler(ValueError)
async def user_error_handler(request: Request, exc: Union[TokenAlreadyExistsError, ValueError]) -> JSONResponse:
    """Handle errors when customer requests options that cannot be processed."""
    return JSONResponse(status_code=400, content={"message": str(exc)})


@app.post(path="/{username}")
async def create_token_for_user(
    username: Annotated[str, Path(title="Username to create token for")],
    request: Request,
    create_request: CreateTokenAdminRequest,
) -> CreateTokenResponse:
    """Admin-only endpoint to create token for a specific user."""
    # Get current user from AWS API Gateway context
    if "aws.event" not in request.scope:
        raise HTTPException(status_code=401, detail="Unauthorized")

    event = request.scope["aws.event"]
    current_user, is_admin_user, _ = get_user_context(event)

    handler = CreateTokenAdminHandler(token_table)
    return handler(username, create_request, current_user, is_admin_user)


@app.post(path="", include_in_schema=False)
@app.post(path="/")
async def create_own_token(request: Request, create_request: CreateTokenUserRequest) -> CreateTokenResponse:
    """User endpoint to create their own token - requires API group membership."""
    # Get current user from AWS API Gateway context
    if "aws.event" not in request.scope:
        raise HTTPException(status_code=401, detail="Unauthorized")

    event = request.scope["aws.event"]
    current_user, is_admin_user, user_groups = get_user_context(event)
    has_api_access = is_api_user(event)

    handler = CreateTokenUserHandler(token_table)
    return handler(create_request, current_user, user_groups, is_admin_user, has_api_access)


@app.get(path="", include_in_schema=False)
@app.get(path="/")
async def list_tokens(request: Request) -> ListTokensResponse:
    """List tokens - admins see all, users see only their own."""
    # Get current user from AWS API Gateway context
    if "aws.event" not in request.scope:
        raise HTTPException(status_code=401, detail="Unauthorized")

    event = request.scope["aws.event"]
    current_user, is_admin_user, _ = get_user_context(event)

    handler = ListTokensHandler(token_table)
    return handler(current_user, is_admin_user)


@app.get(path="/{token_uuid}")
async def get_token(
    token_uuid: Annotated[str, Path(title="The token UUID to get details for")], request: Request
) -> TokenInfo:
    """Get specific token details."""
    # Get current user from AWS API Gateway context
    if "aws.event" not in request.scope:
        raise HTTPException(status_code=401, detail="Unauthorized")

    event = request.scope["aws.event"]
    current_user, is_admin_user, _ = get_user_context(event)

    handler = GetTokenHandler(token_table)
    return handler(token_uuid, current_user, is_admin_user)


@app.delete(path="/{token_uuid}")
async def delete_token(
    token_uuid: Annotated[str, Path(title="The token UUID to delete")], request: Request
) -> DeleteTokenResponse:
    """Delete a token."""
    # Get current user from AWS API Gateway context
    if "aws.event" not in request.scope:
        raise HTTPException(status_code=401, detail="Unauthorized")

    event = request.scope["aws.event"]
    current_user, is_admin_user, _ = get_user_context(event)

    handler = DeleteTokenHandler(token_table)
    return handler(token_uuid, current_user, is_admin_user)


handler = Mangum(app, lifespan="off", api_gateway_base_path="/api-tokens")
docs = Mangum(app, lifespan="off")
