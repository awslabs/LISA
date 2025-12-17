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

import logging
from datetime import timedelta
from typing import Optional
from uuid import uuid4

from boto3.dynamodb.conditions import Key
from utilities.auth import generate_token, hash_token
from utilities.time import now_seconds

from .domain_objects import (
    CreateTokenAdminRequest,
    CreateTokenResponse,
    CreateTokenUserRequest,
    DeleteTokenResponse,
    ListTokensResponse,
    TokenInfo,
)
from .exception import ForbiddenError, TokenAlreadyExistsError, TokenNotFoundError, UnauthorizedError

logger = logging.getLogger(__name__)


def default_expiration() -> int:
    return now_seconds() + timedelta(days=90)


class CreateTokenAdminHandler:
    """Admin creates token for any user or system"""

    def __init__(self, token_table):
        self.token_table = token_table

    def _get_user_token(self, username: str) -> Optional[dict]:
        """Query for existing token by username using GSI"""
        response = self.token_table.query(
            IndexName="username-index", KeyConditionExpression=Key("username").eq(username), Limit=1
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

        # Generate token, hash, and UUID
        token = generate_token()
        token_hash = hash_token(token)
        token_uuid = str(uuid4())

        created_date = now_seconds()
        expiration = request.tokenExpiration

        # Store in DynamoDB
        item = {
            "token": token_hash,
            "tokenUUID": token_uuid,
            "tokenExpiration": expiration,
            "createdDate": created_date,
            "createdBy": created_by,
            "username": username,
            "groups": request.groups,
            "name": request.name,
            "isSystemToken": request.isSystemToken,
        }
        self.token_table.put_item(Item=item)

        # Return response with actual token (only time it's shown)
        return CreateTokenResponse(
            token=token,  # Plain text token - shown ONLY once
            tokenUUID=token_uuid,
            tokenExpiration=expiration,
            createdDate=created_date,
            username=username,
            name=request.name,
            groups=request.groups,
            isSystemToken=request.isSystemToken,
        )


class CreateTokenUserHandler:
    """User creates their own token"""

    def __init__(self, token_table):
        self.token_table = token_table

    def _get_user_token(self, username: str) -> Optional[dict]:
        """Query for existing token by username using GSI"""
        response = self.token_table.query(
            IndexName="username-index", KeyConditionExpression=Key("username").eq(username), Limit=1
        )
        items = response.get("Items", [])
        return items[0] if items else None

    def __call__(
        self, request: CreateTokenUserRequest, username: str, user_groups: list[str], is_admin: bool, is_api_user: bool
    ):
        # Authorization: User must be admin or in apiGroup
        if not is_admin and not is_api_user:
            raise ForbiddenError("User must be in the API group to create tokens")

        # Check if user already has a token
        existing = self._get_user_token(username)
        if existing:
            raise TokenAlreadyExistsError("Token for user already exists. Delete it first to create a new one.")

        # Generate token, hash, and UUID
        token = generate_token()
        token_hash = hash_token(token)
        token_uuid = str(uuid4())

        created_date = now_seconds()
        expiration = request.tokenExpiration

        item = {
            "token": token_hash,
            "tokenUUID": token_uuid,
            "tokenExpiration": expiration,
            "createdDate": created_date,
            "createdBy": username,
            "username": username,  # User creates token for themselves
            "groups": user_groups,  # Copied from user's actual groups
            "name": request.name,
            "isSystemToken": False,  # Always false for user-created tokens
        }
        self.token_table.put_item(Item=item)

        return CreateTokenResponse(
            token=token,
            tokenUUID=token_uuid,
            tokenExpiration=expiration,
            createdDate=created_date,
            username=username,
            name=request.name,
            groups=user_groups,
            isSystemToken=False,
        )


class ListTokensHandler:
    """List tokens - admins see all, users see only their own"""

    def __init__(self, token_table):
        self.token_table = token_table

    def __call__(self, username: str, is_admin: bool) -> ListTokensResponse:
        current_time = now_seconds()

        if is_admin:
            # Return all tokens for admins
            response = self.token_table.scan()
        else:
            # Users only see their own token
            response = self.token_table.query(
                IndexName="username-index", KeyConditionExpression=Key("username").eq(username)
            )

        items = response.get("Items", [])

        tokens = []
        for item in items:
            token_expiration = item.get("tokenExpiration", default_expiration())

            # Determine if token is legacy (no tokenUUID)
            is_legacy = not bool(item.get("tokenUUID"))

            # For legacy tokens, use token attribute; for modern tokens use the name field
            token_name = item["token"] if is_legacy else item.get("name", "Unnamed Token")

            token_info = TokenInfo(
                tokenUUID=item.get("tokenUUID", "—"),
                tokenExpiration=token_expiration,
                createdDate=item.get("createdDate", 0),
                username=item.get("username", "—"),
                createdBy=item.get("createdBy", "—"),
                name=token_name,
                groups=item.get("groups", []),
                isSystemToken=item.get("isSystemToken", False),
                isExpired=token_expiration < current_time,
                isLegacy=is_legacy,
            )
            tokens.append(token_info)

        return ListTokensResponse(tokens=tokens)


class GetTokenHandler:
    """Get specific token details"""

    def __init__(self, token_table):
        self.token_table = token_table

    def __call__(self, token_uuid: str, username: str, is_admin: bool) -> TokenInfo:
        item = None

        # Try to find by tokenUUID (modern tokens) using scan with filter
        try:
            response = self.token_table.scan(FilterExpression=Key("tokenUUID").eq(token_uuid), Limit=1)
            items = response.get("Items", [])
            if items:
                item = items[0]
        except Exception as e:
            # Scan failed, continue to fallback to legacy token lookup
            logger.debug(f"Scan by tokenUUID failed, trying legacy lookup: {e}")

        # If not found, try direct lookup by token attribute (legacy tokens)
        if not item:
            try:
                response = self.token_table.get_item(Key={"token": token_uuid})
                if "Item" in response:
                    item = response["Item"]
            except Exception:
                # Legacy token lookup failed
                item = None

        if not item:
            raise TokenNotFoundError("Token not found")

        # Authorization: admin sees all, user sees only their own
        if not is_admin and item.get("username") != username:
            raise TokenNotFoundError("Token not found")

        current_time = now_seconds()

        token_expiration = item.get("tokenExpiration", default_expiration())

        # Determine if token is legacy (no tokenUUID)
        is_legacy = not bool(item.get("tokenUUID"))

        # For legacy tokens, use token attribute as name; for modern tokens use the name field
        token_name = item["token"] if is_legacy else item.get("name", "Unnamed Token")

        return TokenInfo(
            tokenUUID=item.get("tokenUUID", "—"),
            tokenExpiration=token_expiration,
            createdDate=item.get("createdDate", 0),
            username=item.get("username", "—"),
            createdBy=item.get("createdBy", "—"),
            name=token_name,
            groups=item.get("groups", []),
            isSystemToken=item.get("isSystemToken", False),
            isExpired=token_expiration < current_time,
            isLegacy=is_legacy,
        )


class DeleteTokenHandler:
    """Delete token - handles both modern and legacy tokens"""

    def __init__(self, token_table):
        self.token_table = token_table

    def __call__(self, token_uuid: str, username: str, is_admin: bool) -> DeleteTokenResponse:
        item = None

        # Try to find by tokenUUID (modern tokens) using scan with filter
        try:
            response = self.token_table.scan(FilterExpression=Key("tokenUUID").eq(token_uuid), Limit=1)
            items = response.get("Items", [])
            if items:
                item = items[0]
        except Exception as e:
            # Scan failed, continue to fallback to legacy token lookup
            logger.debug(f"Scan by tokenUUID failed, trying legacy lookup: {e}")

        # If not found, try direct lookup by token attribute (legacy tokens)
        if not item:
            try:
                response = self.token_table.get_item(Key={"token": token_uuid})
                if "Item" in response:
                    item = response["Item"]
            except Exception as e:
                # Legacy token lookup failed - this is expected if token doesn't exist
                logger.debug(f"Legacy token lookup failed for token {token_uuid}: {e}")
                item = None

        if not item:
            raise TokenNotFoundError("Token not found")

        # Determine if token is legacy (no tokenUUID field)
        is_legacy = not bool(item.get("tokenUUID"))

        # Only admins can delete legacy tokens, since they "belong to nobody"
        if is_legacy and not is_admin:
            raise ForbiddenError("Only administrators can delete legacy tokens.")

        # For modern tokens, check ownership
        if not is_legacy and not is_admin and item.get("username") != username:
            raise TokenNotFoundError("Token not found")

        # Delete from DynamoDB using the hash (PK)
        token_hash = item["token"]
        self.token_table.delete_item(Key={"token": token_hash})

        # Return identifier - use tokenUUID for modern tokens, token attribute for legacy
        return_identifier = item.get("tokenUUID") or token_hash[:16]
        return DeleteTokenResponse(message="Token deleted successfully", tokenUUID=return_identifier)
