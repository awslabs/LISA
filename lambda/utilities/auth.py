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

from utilities.common_functions import get_groups
from utilities.exceptions import HTTPException

logger = logging.getLogger(__name__)


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


def admin_only(func: Callable) -> Callable:
    """Annotation to wrap is_admin"""

    @wraps(func)
    def wrapper(event: Dict[str, Any], context: Dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        if not is_admin(event):
            raise HTTPException(status_code=403, message="User does not have permission to access this repository")
        return func(event, context, *args, **kwargs)

    return wrapper
