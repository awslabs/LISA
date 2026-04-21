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

"""Authentication helpers for the LISA SDK.

Provides:
- Cognito interactive login (get_cognito_token)
- Management-key auth via AWS Secrets Manager + DynamoDB token registration
  (get_management_key, create_api_token, setup_authentication)
"""

import getpass
import logging
import time
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


def get_cognito_token(client_id: str, username: str, region: str = "us-east-1") -> dict[str, Any]:
    """Get a token from Cognito.

    Parameters
    ----------
    client_id : str
        Cognito client ID.

    username : str
        Cognito username.

    region : str, default="us-east-1"
        AWS region.

    Returns
    -------
    Dict[str, Any]
        Token response from cognito.
    """
    cognito = boto3.client("cognito-idp", region_name=region)
    token_response = cognito.initiate_auth(
        AuthFlow="USER_PASSWORD_AUTH",
        ClientId=client_id,
        AuthParameters={
            "USERNAME": username,
            "PASSWORD": getpass.getpass("Enter your password: "),
        },
    )
    return token_response  # type: ignore


def get_management_key(
    deployment_name: str,
    region: str | None = None,
    deployment_stage: str | None = None,
) -> str:
    """Retrieve the LISA management key from AWS Secrets Manager.

    Tries several secret-name patterns based on deployment name and stage.

    Parameters
    ----------
    deployment_name : str
        The LISA deployment name.
    region : str | None
        AWS region. Uses boto3 default if *None*.
    deployment_stage : str | None
        Deployment stage. When provided an additional pattern is tried first.

    Returns
    -------
    str
        The management API key.

    Raises
    ------
    RuntimeError
        If none of the secret-name patterns resolve.
    """

    secrets_client = boto3.client("secretsmanager", region_name=region) if region else boto3.client("secretsmanager")

    patterns: list[str] = []
    if deployment_stage:
        patterns.append(f"{deployment_stage}-{deployment_name}-management-key")
    patterns.extend(
        [
            f"{deployment_name}-lisa-management-key",
            f"{deployment_name}-management-key",
            f"lisa-{deployment_name}-management-key",
        ]
    )

    last_error: Exception | None = None
    for secret_name in patterns:
        try:
            response = secrets_client.get_secret_value(SecretId=secret_name)
            secret_string = response.get("SecretString")
            if not isinstance(secret_string, str):
                raise RuntimeError(f"Secret '{secret_name}' does not contain a SecretString ")
            logger.debug("Retrieved management key from %s", secret_name)
            return secret_string
        except ClientError as exc:
            last_error = exc
            logger.debug("Secret %s not found, trying next pattern...", secret_name)
            continue
        except Exception as exc:
            raise RuntimeError(f"Unexpected error retrieving secret '{secret_name}': {type(exc).__name__}") from exc

    raise RuntimeError(f"Could not find management key. Tried: {', '.join(patterns)}") from last_error


def create_api_token(
    deployment_name: str,
    api_key: str,
    region: str | None = None,
    ttl_seconds: int = 3600,
) -> str:
    """Register an API token in DynamoDB with an expiration TTL.

    Parameters
    ----------
    deployment_name : str
        The LISA deployment name (used to derive the token table name).
    api_key : str
        The management API key to register.
    region : str | None
        AWS region. Uses boto3 default if *None*.
    ttl_seconds : int
        Time-to-live in seconds (default 1 hour).

    Returns
    -------
    str
        The registered API token (same as *api_key*).

    Raises
    ------
    Exception
        If the DynamoDB put_item call fails.
    """
    dynamodb = boto3.resource("dynamodb", region_name=region) if region else boto3.resource("dynamodb")
    table_name = f"{deployment_name}-LISAApiBaseTokenTable"
    table = dynamodb.Table(table_name)

    expiration_time = int(time.time()) + ttl_seconds
    table.put_item(Item={"token": api_key, "tokenExpiration": expiration_time})
    logger.debug("Created API token with expiration: %s", expiration_time)
    return api_key


def setup_authentication(
    deployment_name: str,
    region: str | None = None,
    deployment_stage: str | None = None,
) -> dict[str, str]:
    """Set up authentication headers for LISA API calls.

    Fetches the management key from Secrets Manager and optionally registers
    it in DynamoDB for token-based auth tracking.

    Parameters
    ----------
    deployment_name : str
        The LISA deployment name.
    region : str | None
        AWS region. Uses boto3 default if *None*.
    deployment_stage : str | None
        Deployment stage (optional).

    Returns
    -------
    dict[str, str]
        Authentication headers (``Api-Key`` and ``Authorization``).

    Raises
    ------
    RuntimeError
        If the management key cannot be retrieved.
    """
    logger.debug("Setting up authentication for deployment: %s", deployment_name)

    api_key = get_management_key(deployment_name, region, deployment_stage)

    try:
        create_api_token(deployment_name, api_key, region)
    except ClientError as exc:
        logger.warning("Failed to create DynamoDB token (proceeding anyway): %s", type(exc).__name__)
    except Exception as exc:
        logger.warning("Unexpected error creating DynamoDB token (proceeding anyway): %s", type(exc).__name__)

    headers = {"Api-Key": api_key, "Authorization": api_key}
    logger.debug("Authentication setup completed")
    return headers
