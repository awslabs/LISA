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
import json
import logging
import os
import ssl
from functools import cache
from typing import Any, Dict, Optional

import boto3
import create_env_variables  # noqa: F401
import jwt
import requests
from botocore.exceptions import ClientError
from utilities.common_functions import authorization_wrapper, get_id_token, retry_config

logger = logging.getLogger(__name__)

secrets_manager = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)


@authorization_wrapper
def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:  # type: ignore [no-untyped-def]
    """Handle authorization for REST API."""
    logger.info("REST API authorization handler started")

    requested_resource = event["resource"]
    request_method = event["httpMethod"]

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

    deny_policy = generate_policy(effect="Deny", resource=event["methodArn"])
    groups: str
    if id_token in get_management_tokens():
        username = "lisa-management-token"
        # Add management token to Admin groups
        groups = json.dumps([admin_group])
        allow_policy = generate_policy(effect="Allow", resource=event["methodArn"], username=username)
        allow_policy["context"] = {"username": username, "groups": groups}
        logger.debug(f"Generated policy: {allow_policy}")
        return allow_policy

    if jwt_data := id_token_is_valid(id_token=id_token, client_id=client_id, authority=authority):
        is_admin_user = is_admin(jwt_data, admin_group, jwt_groups_property)
        groups = json.dumps(get_property_path(jwt_data, jwt_groups_property) or [])
        username = find_jwt_username(jwt_data)
        allow_policy = generate_policy(effect="Allow", resource=event["methodArn"], username=username)
        allow_policy["context"] = {"username": username, "groups": groups}

        if requested_resource.startswith("/models") and not is_admin_user:
            # non-admin users can still list models
            if event["path"].rstrip("/") != "/models":
                logger.info(f"Deny access to {username} due to non-admin accessing /models api.")
                return deny_policy
        if requested_resource.startswith("/configuration") and request_method == "PUT" and not is_admin_user:
            logger.info(f"Deny access to {username} due to non-admin trying to update configuration.")
            return deny_policy
        logger.debug(f"Generated policy: {allow_policy}")
        logger.info(f"REST API authorization handler completed with 'Allow' for resource {event['methodArn']}")
        return allow_policy

    logger.info(f"REST API authorization handler completed with 'Deny' for resource {event['methodArn']}")
    return deny_policy


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


def id_token_is_valid(*, id_token: str, client_id: str, authority: str) -> Dict[str, Any] | None:
    """Check whether an ID token is valid and return decoded data."""
    if not jwt.algorithms.has_crypto:
        logger.error("No crypto support for JWT, please install the cryptography dependency")
        return None
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
        return None

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
            algorithms=["RS256", "RS512"],
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
        return None


def is_admin(jwt_data: dict[str, Any], admin_group: str, jwt_groups_property: str) -> bool:
    """Check if the user is an admin."""
    return admin_group in (get_property_path(jwt_data, jwt_groups_property) or [])


def get_property_path(data: dict[str, Any], property_path: str) -> Optional[Any]:
    """Get the value represented by a property path."""
    props = property_path.split(".")
    current_node = data
    for prop in props:
        if prop in current_node:
            current_node = current_node[prop]
        else:
            return None

    return current_node


def find_jwt_username(jwt_data: dict[str, str]) -> str:
    """Find the username in the JWT. If the key 'username' doesn't exist, return 'sub', which will be a UUID"""
    username = None
    if "username" in jwt_data:
        username = jwt_data.get("username")
    if "cognito:username" in jwt_data:
        username = jwt_data.get("cognito:username")
    else:
        username = jwt_data.get("sub")

    if not username:
        raise ValueError("No username found in JWT")

    return username


@cache
def get_management_tokens() -> list[str]:
    """Return secret management tokens if they exist."""
    secret_tokens: list[str] = []
    secret_id = os.environ.get("MANAGEMENT_KEY_NAME")

    try:
        secret_tokens.append(
            secrets_manager.get_secret_value(SecretId=secret_id, VersionStage="AWSCURRENT")["SecretString"]
        )
        try:
            secret_tokens.append(
                secrets_manager.get_secret_value(SecretId=secret_id, VersionStage="AWSPREVIOUS")["SecretString"]
            )
        except Exception:
            logger.info("No previous management token version found")
    except ClientError as e:
        logger.warning(f"Unable to fetch {secret_id}. {e.response['Error']['Code']}: {e.response['Error']['Message']}")

    return secret_tokens
