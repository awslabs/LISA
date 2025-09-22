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

"""Authentication for FastAPI app."""
import os
import ssl
import sys
from datetime import datetime
from enum import Enum
from functools import lru_cache
from pathlib import Path
from time import time
from typing import Any, Dict, Optional

import boto3
import jwt
import requests
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from starlette.status import HTTP_401_UNAUTHORIZED

from .utils.decorators import singleton

TOKEN_EXPIRATION_NAME = "tokenExpiration"  # nosec B105
TOKEN_TABLE_NAME = "TOKEN_TABLE_NAME"  # nosec B105
USE_AUTH = "USE_AUTH"


logger_level = os.environ.get("LOG_LEVEL", "INFO")
logger.configure(
    handlers=[
        {
            "sink": sys.stdout,
            "format": ("<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {message}"),
            "level": logger_level.upper(),
        }
    ]
)


# The following are field names, not passwords or tokens
class AuthHeaders(Enum):
    """API key header names."""

    AUTHORIZATION = "Authorization"  # OpenAI Bearer token format, collides with IdP, but that's okay for this use case
    API_KEY = "Api-Key"  # pragma: allowlist secret # Azure key format, can be used with Continue IDE plugin

    @classmethod
    def values(cls) -> list[str]:
        """Return list of header values."""
        return [header.value for header in cls]


def is_idp_used() -> bool:
    """Get if the identity provider is being used based on environment variable."""
    return os.environ.get(USE_AUTH, "false").lower() == "true"


if not jwt.algorithms.has_crypto:
    logger.error("No crypto support for JWT.")
    raise RuntimeError("No crypto support for JWT.")


def get_oidc_metadata(cert_path: Optional[str] = None) -> Dict[str, Any]:
    """Get OIDC endpoints and metadata from authority."""
    authority = os.environ.get("AUTHORITY")
    resp = requests.get(f"{authority}/.well-known/openid-configuration", verify=cert_path or True, timeout=30)
    resp.raise_for_status()
    return resp.json()  # type: ignore


def get_jwks_client() -> jwt.PyJWKClient:
    """Get JWK Client for JWT signing operations."""
    if "SSL_CERT_FILE" not in os.environ:
        cert_path = None
        logger.info("Using default certificate for SSL verification.")
    else:
        cert_path = str(Path(os.environ["SSL_CERT_FILE"]).absolute())
        logger.info("Using self-signed certificate for SSL verification.")
    ssl_context = ssl.create_default_context()
    if cert_path:
        ssl_context.load_verify_locations(cert_path)
    oidc_metadata = get_oidc_metadata(cert_path)
    return jwt.PyJWKClient(oidc_metadata["jwks_uri"], cache_jwk_set=True, lifespan=360, ssl_context=ssl_context)


def id_token_is_valid(
    id_token: str, client_id: str, authority: str, jwks_client: jwt.PyJWKClient
) -> Optional[Dict[str, Any]]:
    """Check whether an ID token is valid and return decoded data."""
    logger.info(f"Auth Token: {id_token}")
    try:
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        data: Dict[str, Any] = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            issuer=authority,
            audience=client_id,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_nbf": True,
                "verify_iat": True,
                "verify_aud": True,
                "verify_iss": True,
            },
        )
        return data
    except (jwt.exceptions.PyJWTError, jwt.exceptions.DecodeError) as e:
        logger.exception(e)
        return None


def is_user_in_group(jwt_data: dict[str, Any], group: str, jwt_groups_property: str) -> bool:
    """Check if the user is in group."""
    props = jwt_groups_property.split(".")
    current_node = jwt_data
    for prop in props:
        if prop in current_node:
            current_node = current_node[prop]
        else:
            return False
    return group in current_node


def get_authorization_token(headers: Dict[str, str], header_name: str = AuthHeaders.AUTHORIZATION.value) -> str:
    """Get Bearer token from Authorization headers if it exists."""
    if header_name in headers:
        return headers.get(header_name, "").removeprefix("Bearer").strip()
    return headers.get(header_name.lower(), "").removeprefix("Bearer").strip()


class OIDCHTTPBearer(HTTPBearer):
    """OIDC based bearer token authenticator."""

    def __init__(self, authority: Optional[str] = None, client_id: Optional[str] = None, **kwargs: Dict[str, Any]):
        super().__init__(**kwargs)
        self.authority = authority or os.environ.get("AUTHORITY", "")
        self.client_id = client_id or os.environ.get("CLIENT_ID", "")
        self.jwks_client = get_jwks_client()

    async def id_token_is_valid(self, request: Request) -> Optional[Dict[str, Any]]:
        """Check whether an ID token is valid and return decoded data."""
        http_auth_creds = await super().__call__(request)
        id_token = http_auth_creds.credentials
        logger.info(f"Auth Token: {id_token}")
        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(id_token)
            data: Dict[str, Any] = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=["RS256"],
                issuer=self.authority,
                audience=self.client_id,
                options={
                    "verify_signature": True,
                    "verify_exp": True,
                    "verify_nbf": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
            return data
        except (jwt.exceptions.PyJWTError, jwt.exceptions.DecodeError) as e:
            logger.exception(e)
            return None


class ApiTokenAuthorizer:
    """Class for checking API tokens against a DynamoDB table of API Tokens.

    For the Token database, only a string value in the "token" field is required. Optionally,
    customers may put a UNIX timestamp (in seconds) in a "tokenExpiration" field so that the
    API key becomes invalid after a specified time.
    """

    def __init__(self) -> None:
        ddb_resource = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"])
        self._token_table = ddb_resource.Table(os.environ[TOKEN_TABLE_NAME])
        self._initialized = True

    def _get_token_info(self, token: str) -> Any:
        """Return DDB entry for token if it exists."""
        ddb_response = self._token_table.get_item(Key={"token": token}, ReturnConsumedCapacity="NONE")
        return ddb_response.get("Item", None)

    def is_valid_api_token(self, headers: Dict[str, str]) -> bool:
        """Return if API Token from request headers is valid if found."""

        for header_name in AuthHeaders.values():
            token = get_authorization_token(headers, header_name)

            logger.info(f"API Auth Token: {token}")
            if token:
                token_info = self._get_token_info(token)
                if token_info:
                    token_expiration = int(token_info.get(TOKEN_EXPIRATION_NAME, datetime.max.timestamp()))
                    current_time = int(datetime.now().timestamp())
                    if current_time < token_expiration:  # token has not expired yet
                        return True
        return False


@lru_cache(maxsize=1)
def get_management_tokens(cache_key: int) -> list[str]:
    """Return secret management tokens if they exist."""
    logger.info(f"Updating management tokens cache for key {cache_key}")
    secrets_manager = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"])
    secret_tokens = []
    try:
        secret_tokens.append(
            secrets_manager.get_secret_value(SecretId=os.environ.get("MANAGEMENT_KEY_NAME"), VersionStage="AWSCURRENT")[
                "SecretString"
            ]
        )
        secret_tokens.append(
            secrets_manager.get_secret_value(
                SecretId=os.environ.get("MANAGEMENT_KEY_NAME"), VersionStage="AWSPREVIOUS"
            )["SecretString"]
        )
    except Exception:
        logger.info(f"No previous secret version for {os.environ.get('MANAGEMENT_KEY_NAME')}")

    return secret_tokens


class ManagementTokenAuthorizer:
    """Class for checking Management tokens against a SecretsManager secret."""

    def __init__(self) -> None:
        pass

    def is_valid_api_token(self, headers: Dict[str, str]) -> bool:
        """Return if API Token from request headers is valid if found."""
        # Fetch the management token once an hour
        cache_key = int(time() // 3600)
        secret_tokens = get_management_tokens(cache_key)
        token = get_authorization_token(headers)
        return token in secret_tokens


@singleton
class Authorizer:
    """Composite authenticator that tries multiple authentication methods in order."""

    def __init__(self) -> None:
        self.client_id = os.environ.get("CLIENT_ID", "")
        self.authority = os.environ.get("AUTHORITY", "")
        self.admin_group = os.environ.get("ADMIN_GROUP", "")
        self.user_group = os.environ.get("USER_GROUP", "")
        self.jwt_groups_property = os.environ.get("JWT_GROUPS_PROP", "")
        self.use_idp = is_idp_used()

        self.token_authorizer = ApiTokenAuthorizer()
        self.management_token_authorizer = ManagementTokenAuthorizer()
        self.oidc_authorizer = OIDCHTTPBearer(authority=self.authority, client_id=self.client_id)

    async def __call__(self, request: Request) -> Optional[HTTPAuthorizationCredentials]:
        jwt_data = await self.authenticate_request(request)
        return jwt_data

    async def authenticate_request(self, request: Request) -> Optional[Dict[str, Any]]:
        """Authenticate request and return JWT data if OIDC, None if API/management token."""
        if not self.use_idp:
            return None

        # First try API tokens
        logger.info("Try API Auth Token...")
        if self.token_authorizer.is_valid_api_token(request.headers):
            logger.info("Valid API token")
            return None

        # Then try management tokens
        logger.info("Try Management Auth Token...")
        if self.management_token_authorizer.is_valid_api_token(request.headers):
            logger.info("Valid Management token")
            return None

        # Finally try OIDC Bearer tokens
        logger.info("Try OIDC Auth Token...")
        jwt_data = await self.oidc_authorizer.id_token_is_valid(request)
        if jwt_data:
            logger.info("Valid OIDC token")
            return jwt_data

        raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    def _log_access_attempt(
        self, request: Request, auth_method: str, user_id: str, endpoint: str, success: bool, reason: str = ""
    ) -> None:
        """Centralized logging for all authentication attempts."""
        status = "SUCCESS" if success else "FAILED"
        log_msg = f"AUTH {status}: user={user_id} method={auth_method} endpoint={endpoint}"
        if reason:
            log_msg += f" reason={reason}"

        if success:
            logger.info(log_msg)
        else:
            logger.warning(log_msg)

    async def can_access(
        self, request: Request, require_admin: bool, jwt_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Return whether the user is authorized to access the endpoint."""
        endpoint = f"{request.method} {request.url.path}"
        auth_method = "NO_IDP"
        user_id = "anonymous"
        has_access = False
        reason = ""

        if not self.use_idp:
            auth_method = "NO_IDP"
            user_id = "anonymous"
            has_access = True
            reason = "IDP disabled"
        else:
            # Use provided JWT data or authenticate request
            if jwt_data is None:
                jwt_data = await self.authenticate_request(request)

            if not jwt_data:
                auth_method = "API_TOKEN"
                user_id = "api_user"
                has_access = True
                reason = "Valid API/Management token"
            else:
                auth_method = "OIDC"
                user_id = jwt_data.get("sub", jwt_data.get("username", "unknown"))

                # If user is admin, always allow access
                if is_user_in_group(jwt_data, self.admin_group, self.jwt_groups_property):
                    has_access = True
                    reason = "Admin user"
                # If admin is required but user is not admin, deny access
                elif require_admin:
                    has_access = False
                    reason = "Admin required"
                # For non-admin requests, check user group
                else:
                    has_access = self.user_group == "" or is_user_in_group(
                        jwt_data=jwt_data, group=self.user_group, jwt_groups_property=self.jwt_groups_property
                    )
                    reason = "Valid user group" if has_access else "Invalid user group"

        self._log_access_attempt(request, auth_method, user_id, endpoint, has_access, reason)
        return has_access
