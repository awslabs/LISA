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
import hashlib
import json
import logging
import os
import secrets
from functools import wraps
from typing import Any, Callable, Dict, List, Tuple

import boto3
from botocore.config import Config
from utilities.exceptions import HTTPException

logger = logging.getLogger(__name__)

retry_config = Config(
    retries={
        "max_attempts": 3,
        "mode": "standard",
    },
)

secrets_client = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)


def get_username(event: dict) -> str:
    """Get the username from the event."""
    username: str = event.get("requestContext", {}).get("authorizer", {}).get("username", "system")
    return username


def get_groups(event: Any) -> List[str]:
    """Get user groups from event."""
    groups: List[str] = json.loads(event.get("requestContext", {}).get("authorizer", {}).get("groups", "[]"))
    return groups


def is_admin(event: dict) -> bool:
    """Get admin status from event."""
    admin_group = os.environ.get("ADMIN_GROUP", "")
    groups = get_groups(event)
    logger.info(f"User groups: {groups} and admin: {admin_group}")
    return admin_group in groups


def get_user_context(event: Dict[str, Any]) -> Tuple[str, bool, List[str]]:
    """Extract user context from event."""
    return get_username(event), is_admin(event), get_groups(event)


def user_has_group_access(user_groups: List[str], allowed_groups: List[str]) -> bool:
    """
    Check if user has access based on group membership.

    Args:
        user_groups: List of groups the user belongs to
        allowed_groups: List of groups allowed to access the resource

    Returns:
        True if user has access (either no restrictions or user has required group)
    """
    # Public resource (no group restrictions)
    if not allowed_groups:
        return True

    # Check if user has at least one matching group
    return len(set(user_groups).intersection(set(allowed_groups))) > 0


def admin_only(func: Callable) -> Callable:
    """Annotation to wrap is_admin"""

    @wraps(func)
    def wrapper(event: Dict[str, Any], context: Dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        if not is_admin(event):
            raise HTTPException(status_code=403, message="User does not have permission to access this repository")
        return func(event, context, *args, **kwargs)

    return wrapper


def get_management_key() -> str:
    secret_name_param = ssm_client.get_parameter(Name=os.environ["MANAGEMENT_KEY_SECRET_NAME_PS"])
    secret_name = secret_name_param["Parameter"]["Value"]
    secret_response = secrets_client.get_secret_value(SecretId=secret_name)
    return secret_response["SecretString"]  # type: ignore[no-any-return]


# API token utility functions
def generate_token() -> str:
    """Generate cryptographically secure random token (64 bytes = 128 hex chars)"""
    return secrets.token_hex(64)


def hash_token(token: str) -> str:
    """Create SHA-256 hash of token"""
    return hashlib.sha256(token.encode()).hexdigest()


def is_api_user(event: dict) -> bool:
    """Get API user status from event."""
    api_group = os.environ.get("API_GROUP", "")
    groups = get_groups(event)
    logger.info(f"User groups: {groups} and api group: {api_group}")
    return api_group in groups
