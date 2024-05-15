"""
Authentication for FastAPI app.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""
import os
import ssl
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import jwt
import requests
from fastapi import HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from loguru import logger
from starlette.status import HTTP_401_UNAUTHORIZED

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


def api_token_is_valid(headers: Dict[str, str]) -> bool:
    """Return whether valid API Token has been found or not."""
    if "Api-Key" in headers:
        return headers["Api-Key"] == "demoApiTokenChangeMeLater"
    return False


class OIDCHTTPBearer(HTTPBearer):
    """OIDC based bearer token authenticator."""

    def __init__(self, **kwargs: Dict[str, Any]):
        super().__init__(**kwargs)

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
        if api_token_is_valid(request.headers):
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
