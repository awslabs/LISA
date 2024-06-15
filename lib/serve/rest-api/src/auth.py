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
from pathlib import Path
from typing import Any, Dict, Optional

import boto3
import jwt
import requests
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from starlette.status import HTTP_401_UNAUTHORIZED

# The following are field names, not passwords or tokens
API_KEY_HEADER_NAMES = [
    "Authorization",  # OpenAI Bearer token format, collides with IdP, but that's okay for this use case
    "Api-Key",  # pragma: allowlist secret # Azure key format, can be used with Continue IDE plugin
]
TOKEN_EXPIRATION_NAME = "tokenExpiration"  # nosec B105
TOKEN_TABLE_NAME = "TOKEN_TABLE_NAME"  # nosec B105


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


if not jwt.algorithms.has_crypto:
    logger.error("No crypto support for JWT.")
    raise RuntimeError("No crypto support for JWT.")


class OIDCHTTPBearer(HTTPBearer):
    """OIDC based bearer token authenticator."""

    def __init__(self, **kwargs: Dict[str, Any]):
        super().__init__(**kwargs)
        self._token_authorizer = ApiTokenAuthorizer()

        if ("SSL_CERT_DIR" not in os.environ) or ("SSL_CERT_FILE" not in os.environ):
            cert_path = None
            logger.info("Using default certificate for SSL verification.")
        else:
            cert_path = str(Path(os.environ["SSL_CERT_DIR"], os.environ["SSL_CERT_FILE"]).absolute())
            logger.info("Using self-signed certificate for SSL verification.")
        ssl_context = ssl.create_default_context()
        if cert_path:
            ssl_context.load_verify_locations(cert_path)
        oidc_metadata = self.get_oidc_metadata(cert_path)
        self.jwks_client = jwt.PyJWKClient(
            oidc_metadata["jwks_uri"], cache_jwk_set=True, lifespan=360, ssl_context=ssl_context
        )

    async def __call__(self, request: Request) -> Optional[HTTPAuthorizationCredentials]:
        """Verify the provided bearer token or API Key. API Key will take precedence over the bearer token."""
        if self._token_authorizer.is_valid_api_token(request.headers):
            return None  # valid API token, not continuing with OIDC auth
        http_auth_creds = await super().__call__(request)
        if not self.id_token_is_valid(
            id_token=http_auth_creds.credentials, authority=os.environ["AUTHORITY"], client_id=os.environ["CLIENT_ID"]
        ):
            raise HTTPException(status_code=HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        return http_auth_creds

    def get_oidc_metadata(self, cert_path: Optional[str] = None) -> Dict[str, Any]:
        """Get OIDC endpoints and metadata from authority."""
        authority = os.environ.get("AUTHORITY")
        resp = requests.get(f"{authority}/.well-known/openid-configuration", verify=cert_path or True, timeout=30)
        resp.raise_for_status()
        return resp.json()  # type: ignore

    def id_token_is_valid(self, id_token: str, client_id: str, authority: str) -> bool:
        """Check whether an ID token is valid and return decoded data."""
        try:
            signing_key = self.jwks_client.get_signing_key_from_jwt(id_token)
            jwt.decode(
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
            return True
        except jwt.exceptions.PyJWTError as e:
            logger.exception(e)
            return False


class ApiTokenAuthorizer:
    """Class for checking API tokens against a DynamoDB table of API Tokens.

    For the Token database, only a string value in the "token" field is required. Optionally,
    customers may put a UNIX timestamp (in seconds) in a "tokenExpiration" field so that the
    API key becomes invalid after a specified time.
    """

    def __init__(self) -> None:
        ddb_resource = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"])
        self._token_table = ddb_resource.Table(os.environ[TOKEN_TABLE_NAME])

    def _get_token_info(self, token: str) -> Any:
        """Return DDB entry for token if it exists."""
        ddb_response = self._token_table.get_item(Key={"token": token}, ReturnConsumedCapacity="NONE")
        return ddb_response.get("Item", None)

    def is_valid_api_token(self, headers: Dict[str, str]) -> bool:
        """Return if API Token from request headers is valid if found."""
        for header_name in API_KEY_HEADER_NAMES:
            token = headers.get(header_name, "").removeprefix("Bearer").strip()
            if token:
                token_info = self._get_token_info(token)
                if token_info:
                    token_expiration = int(token_info.get(TOKEN_EXPIRATION_NAME, datetime.max.timestamp()))
                    current_time = int(datetime.now().timestamp())
                    if current_time < token_expiration:  # token has not expired yet
                        return True
        return False
