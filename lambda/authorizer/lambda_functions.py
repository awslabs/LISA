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

"""Authorize for REST API."""
import logging
import os
import ssl
from typing import Any, Dict, Union

import create_env_variables  # noqa: F401
import jwt
import requests
from utilities.common_functions import authorization_wrapper, get_id_token

logger = logging.getLogger(__name__)


@authorization_wrapper
def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:  # type: ignore [no-untyped-def]
    """Handle authorization for REST API."""
    logger.info("REST API authorization handler started")

    id_token = get_id_token(event)

    if not id_token:
        logger.warn("Missing id_token in request. Denying access.")
        logger.info(f"REST API authorization handler completed with 'Deny' for resource {event['methodArn']}")
        return generate_policy(effect="Deny", resource=event["methodArn"])

    # TODO: investigate authority case sensitivity
    client_id = os.environ.get("CLIENT_ID", "")
    authority = os.environ.get("AUTHORITY", "")
    admin_group = os.environ.get("ADMIN_GROUP", "")
    jwt_groups_property = os.environ.get("JWT_GROUPS_PROP", "")

    if jwt_data := id_token_is_valid(id_token=id_token, client_id=client_id, authority=authority):
        if is_admin(jwt_data, admin_group, jwt_groups_property):
            logger.info(f"USER IS ADMIN")

        policy = generate_policy(effect="Allow", resource=event["methodArn"], username=jwt_data["sub"])  # type: ignore
        policy["context"] = {"username": jwt_data["sub"]}  # type: ignore [index]

        logger.debug(f"Generated policy: {policy}")
        logger.info(f"REST API authorization handler completed with 'Allow' for resource {event['methodArn']}")
        return policy

    logger.info(f"REST API authorization handler completed with 'Deny' for resource {event['methodArn']}")
    return generate_policy(effect="Deny", resource=event["methodArn"])


def generate_policy(*, effect: str, resource: str, username: str = "username") -> Dict[str, Any]:
    """Generate IAM policy."""
    policy = {
        "principalId": username,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [{"Action": "execute-api:Invoke", "Effect": effect, "Resource": resource}],
        },
    }
    return policy


def id_token_is_valid(*, id_token: str, client_id: str, authority: str) -> Union[Dict[str, Any], bool]:
    """Check whether an ID token is valid and return decoded data."""
    if not jwt.algorithms.has_crypto:
        logger.error("No crypto support for JWT, please install the cryptography dependency")
        return False
    logger.info(f"{authority}/.well-known/openid-configuration")

    # Here we will point to the sponsor bundle if available, defined in the create_env_variables import above
    cert_path = os.getenv("SSL_CERT_FILE", None)
    resp = requests.get(
        f"{authority}/.well-known/openid-configuration",
        verify=cert_path or True,
        timeout=120,
    )
    if resp.status_code != 200:
        logger.error("Could not get OIDC metadata: %s", resp.content)
        return False

    oidc_metadata = resp.json()
    try:
        ctx = ssl.create_default_context()
        if cert_path:
            ctx.load_verify_locations(cert_path)
        jwks_client = jwt.PyJWKClient(oidc_metadata["jwks_uri"], cache_jwk_set=True, lifespan=360, ssl_context=ctx)
        signing_key = jwks_client.get_signing_key_from_jwt(id_token)
        data: dict = jwt.decode(
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
    except jwt.exceptions.PyJWTError as e:
        logger.exception(e)
        return False


def is_admin(jwt_data: dict[str, Any], admin_group: str, jwt_groups_property: str):
    """Check if the user is an admin."""
    if jwt_groups_property in jwt_data:
        return admin_group in jwt_data[jwt_groups_property]
    return False
