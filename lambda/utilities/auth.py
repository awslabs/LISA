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
import os
from functools import wraps
from typing import Any, Callable, Dict

import boto3
from botocore.config import Config
from utilities.common_functions import get_groups
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


def is_admin(event: dict) -> bool:
    """Get admin status from event."""
    admin_group = os.environ.get("ADMIN_GROUP", "")
    groups = get_groups(event)
    logger.info(f"User groups: {groups} and admin: {admin_group}")
    return admin_group in groups


def get_user_context(event: dict) -> tuple[str, bool]:
    """Get the username and admin status from the event.

    Args:
        event: Lambda event containing user authentication

    Returns:
        Tuple of (username, is_admin)
    """
    username = get_username(event)
    admin_status = is_admin(event)
    return username, admin_status


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
    return secret_response["SecretString"]
