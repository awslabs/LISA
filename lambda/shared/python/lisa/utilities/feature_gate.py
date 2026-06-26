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

"""Server-side enforcement of admin-configured feature toggles.

Reads ``enabledComponents`` from the global configuration table and exposes a
``@require_feature(key)`` decorator that returns HTTP 403 when an admin has
disabled the feature, plus an ``is_feature_enabled(key)`` helper.

Security control characteristics (read before changing this module):

- **This is a governance toggle, not an authorization boundary.** Authentication
  and identity are enforced upstream by the API Gateway authorizer; this gate
  only enforces an admin's optional decision to disable a capability.
- **Fail-open by design.** When the config table is unset (``CONFIG_TABLE_NAME``
  absent) or unreachable, features default to enabled. Rationale: a DynamoDB
  outage should degrade governance, not deny all traffic. The empty-on-error
  result is itself cached for the TTL window, so a transient error keeps the
  feature enabled for up to the cache TTL rather than retrying each call.
- **Disable propagation is bounded by the cache TTL (5 minutes).** Because the
  result is cached per warm Lambda instance, disabling a feature can take up to
  the TTL to take effect everywhere. This is not an instantaneous kill switch.
- **Applies to all users, including admins** — disabling the feature is itself
  the governance decision.
"""

import logging
import os
from collections.abc import Callable
from functools import wraps
from typing import Any

import boto3
from cachetools import cached, TTLCache  # type: ignore[import-untyped,unused-ignore]
from lisa.utilities.auth import get_username
from lisa.utilities.aws_helpers import retry_config
from lisa.utilities.exceptions import ForbiddenException

logger = logging.getLogger(__name__)

_dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "us-east-1"), config=retry_config)

# Single-entry, 5-minute TTL cache holding the full enabledComponents dict.
# Matches the cache TTL used by session encryption and the projects config read.
_feature_cache: TTLCache = TTLCache(maxsize=1, ttl=300)


def _get_config_table() -> Any | None:
    """Return the global configuration DynamoDB ``Table`` resource.

    Resolved lazily (not at import time) so the module imports cleanly in
    contexts where ``CONFIG_TABLE_NAME`` is not set, and so tests can patch this
    seam. Returns ``None`` when the env var is absent, which callers treat as
    fail-open.
    """
    table_name = os.environ.get("CONFIG_TABLE_NAME")
    if not table_name:
        # Not an error: CONFIG_TABLE_NAME is intentionally unset in supported
        # topologies where the config table is absent (e.g. RAG deployed without
        # chat), so the gate fails open by design.
        logger.warning("CONFIG_TABLE_NAME not set: defaulting all features to enabled")
        return None
    return _dynamodb.Table(table_name)


@cached(cache=_feature_cache)
def _get_enabled_components() -> dict[str, bool]:
    """Read ``enabledComponents`` from the latest global configuration.

    Returns an empty dict on any error or missing configuration, which causes
    every toggle to fail open (enabled). Result is cached for the TTL window.
    """
    table = _get_config_table()
    if table is None:
        return {}
    try:
        response = table.query(
            KeyConditionExpression="configScope = :scope",
            ExpressionAttributeValues={":scope": "global"},
            ScanIndexForward=False,
            Limit=1,
        )
        items = response.get("Items", [])
        if not items:
            logger.warning("No global configuration found: defaulting all features to enabled")
            return {}
        components: dict[str, bool] = items[0].get("configuration", {}).get("enabledComponents", {})
        return components
    except Exception as error:
        logger.error(f"Failed to read enabledComponents: {error}; defaulting all features to enabled")
        return {}


def is_feature_enabled(feature_key: str) -> bool:
    """Return whether an admin-configured feature toggle is enabled.

    Defaults to ``True`` (fail-open) when the toggle is absent from
    configuration, the configuration is missing, or the config table is
    unreachable.

    Args:
        feature_key: The ``enabledComponents`` key to check, e.g.
            ``"deleteSessionHistory"``.
    """
    components = _get_enabled_components()
    return bool(components.get(feature_key, True))


def require_feature(feature_key: str) -> Callable:
    """Decorator for traditional ``(event, context)`` Lambda handlers.

    Raises :class:`ForbiddenException` (HTTP 403) when ``feature_key`` is
    administratively disabled. Apply it inside ``@api_wrapper`` so the raised
    exception is converted to a 403 response::

        @api_wrapper
        @require_feature("deleteSessionHistory")
        def delete_session(event, context):
            ...

    Feature gates apply to all users, including admins: disabling the feature is
    itself the governance decision.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(event: dict[str, Any], context: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
            if not is_feature_enabled(feature_key):
                logger.warning(
                    f"Feature '{feature_key}' is disabled: rejecting request from user={get_username(event)}"
                )
                raise ForbiddenException(
                    f"This feature has been disabled by your administrator (feature: {feature_key})"
                )
            return func(event, context, *args, **kwargs)

        return wrapper

    return decorator
