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
from functools import wraps
from typing import Any, Callable, Dict, Tuple

<<<<<<< HEAD
import boto3
from botocore.config import Config
from utilities.common_functions import get_groups
=======
>>>>>>> ad9e1a09 (Organize ingestion)
from utilities.exceptions import HTTPException
from .brass_client import BrassClient

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
    """Get admin status from event using BRASS bindle lock authorization."""
    username = get_username(event)
    
    # Check BRASS admin bindle lock using BrassClient directly
    brass_client = BrassClient()
    if brass_client.check_admin_access(username):
        logger.info(f"User {username} granted admin access via BRASS admin bindle lock")
        return True
    
    logger.info(f"User {username} denied admin access - no valid authorization found")
    return False


def get_user_context(event: Dict[str, Any]) -> Tuple[str, bool]:
    """Extract user context from event."""
    return get_username(event), is_admin(event)


def admin_only(func: Callable) -> Callable:
    """Annotation to wrap is_admin"""

    @wraps(func)
    def wrapper(event: Dict[str, Any], context: Dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        if not is_admin(event):
            raise HTTPException(status_code=403, message="User does not have permission to access this repository")
        return func(event, context, *args, **kwargs)

<<<<<<< HEAD
    return wrapper


def get_management_key() -> str:
    secret_name_param = ssm_client.get_parameter(Name=os.environ["MANAGEMENT_KEY_SECRET_NAME_PS"])
    secret_name = secret_name_param["Parameter"]["Value"]
    secret_response = secrets_client.get_secret_value(SecretId=secret_name)
    return secret_response["SecretString"]
=======
    return wrapper
>>>>>>> ad9e1a09 (Organize ingestion)
