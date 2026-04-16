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

"""Per-user rate limiting middleware using an in-memory token bucket.

Runs after authentication so the caller identity is available on ``request.state``.
Each ECS task tracks limits independently — the effective per-user limit across the
fleet is ``N_tasks × RATE_LIMIT_RPM``, which naturally scales with capacity.

Configuration (environment variables):
    RATE_LIMIT_RPM   – sustained requests per minute per user (default 60)
    RATE_LIMIT_BURST – extra burst allowance above the sustained rate (default 10)
    RATE_LIMIT_ENABLED – set to "false" to disable (default "true")
    RATE_LIMIT_OVERRIDES – JSON map of per-user/per-token overrides (default "{}")
        Keys match the user_key format: "token:<tokenUUID>" or "oidc:<sub>" or "user:<username>"
        Values are objects with optional "rpm" and "burst" fields.
        Example: {"token:abc-123": {"rpm": 120, "burst": 20}, "oidc:user-456": {"rpm": 10}}
"""

import json
import os
import time
import threading
from collections.abc import Callable
from typing import Any

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from loguru import logger
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
RATE_LIMIT_RPM = int(os.environ.get("RATE_LIMIT_RPM", "60"))
RATE_LIMIT_BURST = int(os.environ.get("RATE_LIMIT_BURST", "10"))
RATE_LIMIT_ENABLED = os.environ.get("RATE_LIMIT_ENABLED", "true").lower() == "true"

# Per-user overrides: { "token:<uuid>": {"rpm": N, "burst": N}, ... }
def _parse_overrides(raw: str) -> dict[str, dict[str, int]]:
    """Parse the RATE_LIMIT_OVERRIDES JSON env var into a validated dict."""
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            logger.warning("RATE_LIMIT_OVERRIDES is not a JSON object, ignoring")
            return {}
        result: dict[str, dict[str, int]] = {}
        for key, val in parsed.items():
            if not isinstance(val, dict):
                logger.warning(f"RATE_LIMIT_OVERRIDES[{key}] is not an object, skipping")
                continue
            entry: dict[str, int] = {}
            if "rpm" in val:
                entry["rpm"] = int(val["rpm"])
            if "burst" in val:
                entry["burst"] = int(val["burst"])
            result[str(key)] = entry
        return result
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Failed to parse RATE_LIMIT_OVERRIDES: {e}")
        return {}


RATE_LIMIT_OVERRIDES: dict[str, dict[str, int]] = _parse_overrides(
    os.environ.get("RATE_LIMIT_OVERRIDES", "")
)

# Derived: tokens added per second (system default)
_REFILL_RATE = RATE_LIMIT_RPM / 60.0

# Paths exempt from rate limiting
_EXEMPT_PATHS = {"/health", "/health/readiness", "/health/liveliness"}

# Maximum number of tracked users before we prune stale entries
_MAX_BUCKETS = 10_000
# Entries older than this (seconds) are eligible for pruning
_STALE_SECONDS = 300.0


# ---------------------------------------------------------------------------
# Token bucket implementation
# ---------------------------------------------------------------------------

class _TokenBucket:
    """Simple token bucket for a single user.

    Not thread-safe on its own — callers must hold ``_lock``.
    """

    __slots__ = ("tokens", "last_refill")

    def __init__(self, max_tokens: float) -> None:
        self.tokens: float = max_tokens
        self.last_refill: float = time.monotonic()

    def try_consume(self, max_tokens: float, refill_rate: float) -> tuple[bool, float]:
        """Refill and attempt to consume one token.

        Returns ``(allowed, retry_after_seconds)``.
        """
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(max_tokens, self.tokens + elapsed * refill_rate)
        self.last_refill = now

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True, 0.0

        # How long until one token is available
        wait = (1.0 - self.tokens) / refill_rate
        return False, wait


# Global bucket store — keyed by user identity string
_buckets: dict[str, _TokenBucket] = {}
_lock = threading.Lock()


def _get_max_tokens() -> float:
    """Max tokens = sustained rate (per minute converted to bucket size) + burst.

    Returns the system default. For per-user values use ``_get_user_limits``.
    """
    return float(RATE_LIMIT_RPM) + float(RATE_LIMIT_BURST)


def _get_user_limits(user_key: str) -> tuple[float, float, float]:
    """Return (max_tokens, refill_rate, rpm) for a specific user.

    Checks ``RATE_LIMIT_OVERRIDES`` first, falls back to system defaults.
    """
    override = RATE_LIMIT_OVERRIDES.get(user_key)
    if override:
        rpm = override.get("rpm", RATE_LIMIT_RPM)
        burst = override.get("burst", RATE_LIMIT_BURST)
    else:
        rpm = RATE_LIMIT_RPM
        burst = RATE_LIMIT_BURST
    max_tokens = float(rpm) + float(burst)
    refill_rate = rpm / 60.0
    return max_tokens, refill_rate, float(rpm)


def _prune_stale_buckets() -> None:
    """Remove buckets that haven't been touched recently. Must hold ``_lock``."""
    now = time.monotonic()
    stale_keys = [k for k, b in _buckets.items() if (now - b.last_refill) > _STALE_SECONDS]
    for k in stale_keys:
        del _buckets[k]


def _check_rate_limit(user_key: str) -> tuple[bool, float]:
    """Check whether *user_key* is within its rate limit.

    Returns ``(allowed, retry_after_seconds)``.
    Uses per-user overrides from ``RATE_LIMIT_OVERRIDES`` when available.
    """
    max_tokens, refill_rate, _ = _get_user_limits(user_key)

    with _lock:
        if len(_buckets) >= _MAX_BUCKETS:
            _prune_stale_buckets()

        bucket = _buckets.get(user_key)
        if bucket is None:
            bucket = _TokenBucket(max_tokens)
            _buckets[user_key] = bucket

        return bucket.try_consume(max_tokens, refill_rate)


# ---------------------------------------------------------------------------
# User identity extraction
# ---------------------------------------------------------------------------

def _get_user_key(request: Request) -> str | None:
    """Derive a rate-limit key from the authenticated request.

    Returns ``None`` for requests that should bypass rate limiting
    (management tokens, unauthenticated/public paths).
    """
    # Management tokens bypass rate limiting — they're internal automation
    if not hasattr(request.state, "authenticated"):
        return None

    # API token users — key on tokenUUID (unique per key)
    if hasattr(request.state, "api_token_info"):
        token_info = request.state.api_token_info
        token_uuid = token_info.get("tokenUUID")
        if token_uuid:
            return f"token:{token_uuid}"
        # Fallback to username if no UUID (shouldn't happen for valid tokens)
        return f"token:{token_info.get('username', 'unknown')}"

    # OIDC users — key on subject claim
    jwt_data = getattr(request.state, "jwt_data", None)
    if jwt_data and isinstance(jwt_data, dict):
        sub = jwt_data.get("sub") or jwt_data.get("username")
        if sub:
            return f"oidc:{sub}"

    # Fallback to username set by auth middleware
    username = getattr(request.state, "username", None)
    if username:
        return f"user:{username}"

    return None


# ---------------------------------------------------------------------------
# Middleware entry point
# ---------------------------------------------------------------------------

async def rate_limit_middleware(request: Request, call_next: Callable[[Request], Response]) -> Response:
    """Per-user rate limiting middleware.

    Must run **after** authentication middleware so that ``request.state``
    contains the caller identity.
    """
    if not RATE_LIMIT_ENABLED:
        return await call_next(request)

    # Skip exempt paths
    if request.url.path in _EXEMPT_PATHS:
        return await call_next(request)

    # Skip OPTIONS (CORS preflight)
    if request.method == "OPTIONS":
        return await call_next(request)

    user_key = _get_user_key(request)
    if user_key is None:
        # Can't identify user or exempt category — let it through
        return await call_next(request)

    allowed, retry_after = _check_rate_limit(user_key)

    if not allowed:
        logger.warning(f"Rate limit exceeded for {user_key}, retry_after={retry_after:.1f}s")
        return JSONResponse(
            status_code=HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": {
                    "message": "Rate limit exceeded. Please slow down and retry.",
                    "type": "rate_limit_error",
                    "code": "rate_limit_exceeded",
                }
            },
            headers={"Retry-After": str(int(retry_after) + 1)},
        )

    return await call_next(request)
