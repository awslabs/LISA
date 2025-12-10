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

from datetime import datetime, timedelta
from typing import Optional

from boto3.dynamodb.conditions import Key
from utilities.auth import generate_token, hash_token

from .domain_objects import (
    CreateTokenAdminRequest,
    CreateTokenResponse,
    CreateTokenUserRequest,
    DeleteTokenResponse,
    ListTokensResponse,
    TokenInfo,
)
from .exception import ForbiddenError, TokenAlreadyExistsError, TokenNotFoundError, UnauthorizedError


class CreateTokenAdminHandler:
    """Admin creates token for any user or system"""

    def __init__(self, token_table):
        self.token_table = token_table

    def _get_user_token(self, username: str) -> Optional[dict]:
        """Query for existing token by createdFor using GSI"""
        response = self.token_table.query(
            IndexName="createdFor-index", KeyConditionExpression=Key("createdFor").eq(username), Limit=1
        )
        items = response.get("Items", [])
        return items[0] if items else None

    def __call__(self, username: str, request: CreateTokenAdminRequest, created_by: str, is_admin: bool):
        # Authorization: Only admins can create tokens for other users
        if not is_admin:
            raise UnauthorizedError("Only admins can create tokens for other users")

        # Check if user already has a token (unless system token)
        if not request.isSystemToken:
            existing = self._get_user_token(username)
            if existing:
                raise TokenAlreadyExistsError(f"User {username} already has a token")

        # Generate token and hash
        token = generate_token()
        token_hash = hash_token(token)

        # Set defaults
        created_date = int(datetime.now().timestamp())
        expiration = request.tokenExpiration or int((datetime.now() + timedelta(days=90)).timestamp())

        # Store in DynamoDB
        item = {
            "token": token_hash,
            "tokenExpiration": expiration,
            "createdDate": created_date,
            "createdBy": created_by,
            "createdFor": username,
            "groups": request.groups,
            "name": request.name,
            "isSystemToken": request.isSystemToken,
        }
        self.token_table.put_item(Item=item)

        # Return response with actual token (only time it's shown)
        return CreateTokenResponse(
            token=token,  # Plain text token - shown ONLY once
            tokenHash=token_hash,
            tokenExpiration=expiration,
            createdDate=created_date,
            createdFor=username,
            name=request.name,
            groups=request.groups,
            isSystemToken=request.isSystemToken,
        )


class CreateTokenUserHandler:
    """User creates their own token"""

    def __init__(self, token_table):
        self.token_table = token_table

    def _get_user_token(self, username: str) -> Optional[dict]:
        """Query for existing token by createdFor using GSI"""
        response = self.token_table.query(
            IndexName="createdFor-index", KeyConditionExpression=Key("createdFor").eq(username), Limit=1
        )
        items = response.get("Items", [])
        return items[0] if items else None

    def __call__(self, request: CreateTokenUserRequest, username: str, user_groups: list[str], is_admin: bool):
        # Authorization: User must be admin or in api-user group
        if not is_admin and "api-user" not in user_groups:
            raise ForbiddenError("User must be in 'api-user' group to create tokens")

        # Check if user already has a token
        existing = self._get_user_token(username)
        if existing:
            raise TokenAlreadyExistsError("You already have a token. Delete it first to create a new one.")

        # Generate token and hash
        token = generate_token()
        token_hash = hash_token(token)

        # Auto-populate everything
        created_date = int(datetime.now().timestamp())
        expiration = int((datetime.now() + timedelta(days=90)).timestamp())

        item = {
            "token": token_hash,
            "tokenExpiration": expiration,
            "createdDate": created_date,
            "createdBy": username,
            "createdFor": username,  # User creates token for themselves
            "groups": user_groups,  # Copy from user's actual groups
            "name": request.name,
            "isSystemToken": False,  # Always false for user-created tokens
        }
        self.token_table.put_item(Item=item)

        return CreateTokenResponse(
            token=token,
            tokenHash=token_hash,
            tokenExpiration=expiration,
            createdDate=created_date,
            createdFor=username,
            name=request.name,
            groups=user_groups,
            isSystemToken=False,
        )


class ListTokensHandler:
    """List tokens - admins see all, users see only their own"""

    def __init__(self, token_table):
        self.token_table = token_table

    def __call__(self, username: str, is_admin: bool) -> ListTokensResponse:
        current_time = int(datetime.now().timestamp())

        if is_admin:
            # Admin sees all tokens
            response = self.token_table.scan()
        else:
            # User sees only their own tokens
            response = self.token_table.query(
                IndexName="createdFor-index", KeyConditionExpression=Key("createdFor").eq(username)
            )

        items = response.get("Items", [])

        tokens = []
        for item in items:
            # Use .get() to safely access tokenExpiration with a default
            token_expiration = item.get("tokenExpiration", int((datetime.now() + timedelta(days=90)).timestamp()))

            token_info = TokenInfo(
                tokenHash=item["token"],
                tokenExpiration=token_expiration,
                createdDate=item.get("createdDate", 0),
                createdFor=item.get("createdFor", "unknown"),
                createdBy=item.get("createdBy", "unknown"),
                name=item.get("name", "Unnamed Token"),
                groups=item.get("groups", []),
                isSystemToken=item.get("isSystemToken", False),
                isExpired=token_expiration < current_time,
            )
            tokens.append(token_info)

        return ListTokensResponse(tokens=tokens)


class GetTokenHandler:
    """Get specific token details"""

    def __init__(self, token_table):
        self.token_table = token_table

    def __call__(self, token_hash: str, username: str, is_admin: bool) -> TokenInfo:
        # Get token from DynamoDB
        response = self.token_table.get_item(Key={"token": token_hash})
        item = response.get("Item")

        if not item:
            raise TokenNotFoundError("Token not found")

        # Authorization: admin sees all, user sees only their own
        if not is_admin and item.get("createdFor") != username:
            raise TokenNotFoundError("Token not found")

        current_time = int(datetime.now().timestamp())

        # Use .get() to safely access tokenExpiration with a default
        token_expiration = item.get("tokenExpiration", int((datetime.now() + timedelta(days=90)).timestamp()))

        return TokenInfo(
            tokenHash=item["token"],
            tokenExpiration=token_expiration,
            createdDate=item.get("createdDate", 0),
            createdFor=item.get("createdFor", "unknown"),
            createdBy=item.get("createdBy", "unknown"),
            name=item.get("name", "Unnamed Token"),
            groups=item.get("groups", []),
            isSystemToken=item.get("isSystemToken", False),
            isExpired=token_expiration < current_time,
        )


class DeleteTokenHandler:
    """Delete token"""

    def __init__(self, token_table):
        self.token_table = token_table

    def __call__(self, token_hash: str, username: str, is_admin: bool) -> DeleteTokenResponse:
        # Get token first to check ownership
        response = self.token_table.get_item(Key={"token": token_hash})
        item = response.get("Item")

        if not item:
            raise TokenNotFoundError("Token not found")

        # Authorization: admin can delete any, user can delete only their own
        if not is_admin and item.get("createdFor") != username:
            raise TokenNotFoundError("Token not found")

        # Delete from DynamoDB
        self.token_table.delete_item(Key={"token": token_hash})

        return DeleteTokenResponse(message="Token deleted successfully", tokenHash=token_hash)
