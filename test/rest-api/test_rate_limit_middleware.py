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

"""Tests for per-user rate limiting middleware."""
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import Response

# Add the REST API source to the path
rest_api_src = Path(__file__).parent.parent.parent / "lib" / "serve" / "rest-api" / "src"
sys.path.insert(0, str(rest_api_src))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_request(path="/v2/serve/chat/completions", method="POST"):
    """Create a mock request with a clean state object."""
    request = MagicMock()
    request.url.path = path
    request.method = method

    class State:
        pass

    request.state = State()
    return request


def _ok_response():
    return Response(content="ok", status_code=200)


async def _call_next_ok(request):
    return _ok_response()


# ---------------------------------------------------------------------------
# Token bucket unit tests
# ---------------------------------------------------------------------------


class TestTokenBucket:
    """Tests for the _TokenBucket internal class."""

    def test_initial_tokens_available(self):
        from middleware.rate_limit_middleware import _TokenBucket

        bucket = _TokenBucket(max_tokens=10.0)
        allowed, _ = bucket.try_consume(10.0, 1.0)
        assert allowed is True

    def test_exhaustion(self):
        from middleware.rate_limit_middleware import _TokenBucket

        bucket = _TokenBucket(max_tokens=2.0)
        bucket.try_consume(2.0, 1.0)
        bucket.try_consume(2.0, 1.0)
        allowed, retry_after = bucket.try_consume(2.0, 1.0)
        assert allowed is False
        assert retry_after > 0

    def test_refill_over_time(self):
        from middleware.rate_limit_middleware import _TokenBucket

        bucket = _TokenBucket(max_tokens=2.0)
        # Drain all tokens
        bucket.try_consume(2.0, 1.0)
        bucket.try_consume(2.0, 1.0)
        # Simulate time passing by backdating last_refill
        bucket.last_refill = time.monotonic() - 2.0  # 2 seconds ago at 1 token/sec
        allowed, _ = bucket.try_consume(2.0, 1.0)
        assert allowed is True

    def test_tokens_capped_at_max(self):
        from middleware.rate_limit_middleware import _TokenBucket

        bucket = _TokenBucket(max_tokens=5.0)
        # Simulate a long idle period
        bucket.last_refill = time.monotonic() - 1000.0
        bucket.try_consume(5.0, 1.0)
        # Should have been capped at 5, consumed 1 → 4 left
        assert bucket.tokens == pytest.approx(4.0, abs=0.1)

    def test_retry_after_is_reasonable(self):
        from middleware.rate_limit_middleware import _TokenBucket

        refill_rate = 1.0  # 1 token/sec
        bucket = _TokenBucket(max_tokens=1.0)
        bucket.try_consume(1.0, refill_rate)  # drain it
        allowed, retry_after = bucket.try_consume(1.0, refill_rate)
        assert allowed is False
        # Should be ~1 second to get the next token
        assert 0 < retry_after <= 1.1


# ---------------------------------------------------------------------------
# _get_user_key tests
# ---------------------------------------------------------------------------


class TestGetUserKey:
    """Tests for user identity extraction from request state."""

    def test_api_token_user_keyed_on_uuid(self):
        from middleware.rate_limit_middleware import _get_user_key

        request = _make_request()
        request.state.authenticated = True
        request.state.api_token_info = {"tokenUUID": "abc-123", "username": "api-user"}
        assert _get_user_key(request) == "token:abc-123"

    def test_api_token_fallback_to_username(self):
        from middleware.rate_limit_middleware import _get_user_key

        request = _make_request()
        request.state.authenticated = True
        request.state.api_token_info = {"username": "api-user"}
        assert _get_user_key(request) == "token:api-user"

    def test_oidc_user_keyed_on_sub(self):
        from middleware.rate_limit_middleware import _get_user_key

        request = _make_request()
        request.state.authenticated = True
        request.state.jwt_data = {"sub": "user-456", "username": "jdoe"}
        assert _get_user_key(request) == "oidc:user-456"

    def test_oidc_user_fallback_to_username(self):
        from middleware.rate_limit_middleware import _get_user_key

        request = _make_request()
        request.state.authenticated = True
        request.state.jwt_data = {"username": "jdoe"}
        assert _get_user_key(request) == "oidc:jdoe"

    def test_fallback_to_state_username(self):
        from middleware.rate_limit_middleware import _get_user_key

        request = _make_request()
        request.state.authenticated = True
        request.state.username = "fallback-user"
        assert _get_user_key(request) == "user:fallback-user"

    def test_management_token_returns_none(self):
        """Management tokens have no 'authenticated' attr — should bypass."""
        from middleware.rate_limit_middleware import _get_user_key

        request = _make_request()
        # No request.state.authenticated set
        assert _get_user_key(request) is None

    def test_no_identity_returns_none(self):
        from middleware.rate_limit_middleware import _get_user_key

        request = _make_request()
        request.state.authenticated = True
        # No token info, jwt_data, or username
        assert _get_user_key(request) is None


# ---------------------------------------------------------------------------
# Middleware integration tests
# ---------------------------------------------------------------------------


class TestRateLimitMiddleware:
    """Tests for the rate_limit_middleware function."""

    @pytest.fixture(autouse=True)
    def _clear_buckets(self):
        """Clear the global bucket store between tests."""
        import importlib

        mod = importlib.import_module("middleware.rate_limit_middleware")
        mod._buckets.clear()
        yield
        mod._buckets.clear()

    @pytest.mark.asyncio
    async def test_allows_request_within_limit(self):
        from middleware.rate_limit_middleware import rate_limit_middleware

        request = _make_request()
        request.state.authenticated = True
        request.state.api_token_info = {"tokenUUID": "test-uuid", "username": "u"}

        result = await rate_limit_middleware(request, _call_next_ok)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_blocks_after_burst_exceeded(self):
        from middleware.rate_limit_middleware import (
            _get_max_tokens,
            rate_limit_middleware,
        )

        request = _make_request()
        request.state.authenticated = True
        request.state.api_token_info = {"tokenUUID": "burst-test", "username": "u"}

        max_tokens = int(_get_max_tokens())

        # Exhaust the bucket
        for _ in range(max_tokens):
            resp = await rate_limit_middleware(request, _call_next_ok)
            assert resp.status_code == 200

        # Next request should be throttled
        resp = await rate_limit_middleware(request, _call_next_ok)
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers

    @pytest.mark.asyncio
    async def test_429_response_body_format(self):
        """Verify the 429 body is OpenAI-compatible."""
        import json

        from middleware.rate_limit_middleware import (
            _get_max_tokens,
            rate_limit_middleware,
        )

        request = _make_request()
        request.state.authenticated = True
        request.state.api_token_info = {"tokenUUID": "body-test", "username": "u"}

        # Drain bucket
        for _ in range(int(_get_max_tokens())):
            await rate_limit_middleware(request, _call_next_ok)

        resp = await rate_limit_middleware(request, _call_next_ok)
        body = json.loads(resp.body.decode())
        assert body["error"]["type"] == "rate_limit_error"
        assert body["error"]["code"] == "rate_limit_exceeded"

    @pytest.mark.asyncio
    async def test_health_endpoint_bypassed(self):
        from middleware.rate_limit_middleware import rate_limit_middleware

        request = _make_request(path="/health")
        request.state.authenticated = True
        request.state.api_token_info = {"tokenUUID": "health-test", "username": "u"}

        result = await rate_limit_middleware(request, _call_next_ok)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_options_request_bypassed(self):
        from middleware.rate_limit_middleware import rate_limit_middleware

        request = _make_request(method="OPTIONS")
        request.state.authenticated = True
        request.state.api_token_info = {"tokenUUID": "opts-test", "username": "u"}

        result = await rate_limit_middleware(request, _call_next_ok)
        assert result.status_code == 200

    @pytest.mark.asyncio
    async def test_disabled_via_env(self, monkeypatch):
        """When RATE_LIMIT_ENABLED=false, all requests pass through."""
        import importlib

        mod = importlib.import_module("middleware.rate_limit_middleware")

        original = mod.RATE_LIMIT_ENABLED
        mod.RATE_LIMIT_ENABLED = False
        try:
            request = _make_request()
            request.state.authenticated = True
            request.state.api_token_info = {"tokenUUID": "disabled-test", "username": "u"}

            # Even after many requests, should never get 429
            for _ in range(200):
                resp = await mod.rate_limit_middleware(request, _call_next_ok)
                assert resp.status_code == 200
        finally:
            mod.RATE_LIMIT_ENABLED = original

    @pytest.mark.asyncio
    async def test_separate_buckets_per_user(self):
        """Two different users should have independent rate limits."""
        from middleware.rate_limit_middleware import (
            _get_max_tokens,
            rate_limit_middleware,
        )

        max_tokens = int(_get_max_tokens())

        # User A exhausts their bucket
        req_a = _make_request()
        req_a.state.authenticated = True
        req_a.state.api_token_info = {"tokenUUID": "user-a", "username": "a"}
        for _ in range(max_tokens):
            await rate_limit_middleware(req_a, _call_next_ok)

        resp_a = await rate_limit_middleware(req_a, _call_next_ok)
        assert resp_a.status_code == 429

        # User B should still be fine
        req_b = _make_request()
        req_b.state.authenticated = True
        req_b.state.api_token_info = {"tokenUUID": "user-b", "username": "b"}
        resp_b = await rate_limit_middleware(req_b, _call_next_ok)
        assert resp_b.status_code == 200

    @pytest.mark.asyncio
    async def test_management_token_bypassed(self):
        """Management tokens (no authenticated attr) should never be throttled."""
        from middleware.rate_limit_middleware import rate_limit_middleware

        request = _make_request()
        # Management tokens don't set request.state.authenticated

        for _ in range(200):
            resp = await rate_limit_middleware(request, _call_next_ok)
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_oidc_user_rate_limited(self):
        """OIDC users should be rate limited by their sub claim."""
        from middleware.rate_limit_middleware import (
            _get_max_tokens,
            rate_limit_middleware,
        )

        request = _make_request()
        request.state.authenticated = True
        request.state.jwt_data = {"sub": "oidc-user-1"}

        max_tokens = int(_get_max_tokens())
        for _ in range(max_tokens):
            await rate_limit_middleware(request, _call_next_ok)

        resp = await rate_limit_middleware(request, _call_next_ok)
        assert resp.status_code == 429


# ---------------------------------------------------------------------------
# Bucket pruning tests
# ---------------------------------------------------------------------------


class TestBucketPruning:
    """Tests for stale bucket cleanup."""

    @pytest.fixture(autouse=True)
    def _clear_buckets(self):
        import importlib

        mod = importlib.import_module("middleware.rate_limit_middleware")
        mod._buckets.clear()
        yield
        mod._buckets.clear()

    def test_stale_buckets_pruned(self):
        from middleware.rate_limit_middleware import (
            _buckets,
            _prune_stale_buckets,
            _STALE_SECONDS,
            _TokenBucket,
        )

        # Add a stale bucket
        bucket = _TokenBucket(10.0)
        bucket.last_refill = time.monotonic() - _STALE_SECONDS - 10
        _buckets["stale-user"] = bucket

        # Add a fresh bucket
        _buckets["fresh-user"] = _TokenBucket(10.0)

        _prune_stale_buckets()

        assert "stale-user" not in _buckets
        assert "fresh-user" in _buckets


# ---------------------------------------------------------------------------
# Override parsing tests
# ---------------------------------------------------------------------------


class TestParseOverrides:
    """Tests for _parse_overrides JSON parsing."""

    def test_empty_string(self):
        from middleware.rate_limit_middleware import _parse_overrides

        assert _parse_overrides("") == {}

    def test_valid_overrides(self):
        from middleware.rate_limit_middleware import _parse_overrides

        raw = '{"token:abc-123": {"rpm": 120, "burst": 20}, "oidc:user-1": {"rpm": 10}}'
        result = _parse_overrides(raw)
        assert result == {
            "token:abc-123": {"rpm": 120, "burst": 20},
            "oidc:user-1": {"rpm": 10},
        }

    def test_invalid_json(self):
        from middleware.rate_limit_middleware import _parse_overrides

        assert _parse_overrides("not json") == {}

    def test_non_object_root(self):
        from middleware.rate_limit_middleware import _parse_overrides

        assert _parse_overrides("[1, 2, 3]") == {}

    def test_non_object_value_skipped(self):
        from middleware.rate_limit_middleware import _parse_overrides

        raw = '{"token:good": {"rpm": 100}, "token:bad": "not-an-object"}'
        result = _parse_overrides(raw)
        assert "token:good" in result
        assert "token:bad" not in result

    def test_rpm_only_override(self):
        from middleware.rate_limit_middleware import _parse_overrides

        raw = '{"token:x": {"rpm": 200}}'
        result = _parse_overrides(raw)
        assert result["token:x"] == {"rpm": 200}

    def test_burst_only_override(self):
        from middleware.rate_limit_middleware import _parse_overrides

        raw = '{"token:x": {"burst": 50}}'
        result = _parse_overrides(raw)
        assert result["token:x"] == {"burst": 50}


# ---------------------------------------------------------------------------
# _get_user_limits tests
# ---------------------------------------------------------------------------


class TestGetUserLimits:
    """Tests for per-user limit resolution with overrides."""

    @pytest.fixture(autouse=True)
    def _set_overrides(self):
        import importlib

        mod = importlib.import_module("middleware.rate_limit_middleware")
        self._mod = mod
        self._original_overrides = mod.RATE_LIMIT_OVERRIDES.copy()
        yield
        mod.RATE_LIMIT_OVERRIDES = self._original_overrides

    def test_no_override_returns_system_defaults(self):
        mod = self._mod
        mod.RATE_LIMIT_OVERRIDES = {}
        max_tokens, refill_rate, rpm = mod._get_user_limits("token:unknown")
        assert rpm == float(mod.RATE_LIMIT_RPM)
        assert max_tokens == float(mod.RATE_LIMIT_RPM) + float(mod.RATE_LIMIT_BURST)
        assert refill_rate == mod.RATE_LIMIT_RPM / 60.0

    def test_rpm_override_applied(self):
        mod = self._mod
        mod.RATE_LIMIT_OVERRIDES = {"token:fast-user": {"rpm": 200}}
        max_tokens, refill_rate, rpm = mod._get_user_limits("token:fast-user")
        assert rpm == 200.0
        assert refill_rate == 200.0 / 60.0
        # burst falls back to system default
        assert max_tokens == 200.0 + float(mod.RATE_LIMIT_BURST)

    def test_burst_override_applied(self):
        mod = self._mod
        mod.RATE_LIMIT_OVERRIDES = {"token:bursty": {"burst": 50}}
        max_tokens, refill_rate, rpm = mod._get_user_limits("token:bursty")
        assert rpm == float(mod.RATE_LIMIT_RPM)
        assert max_tokens == float(mod.RATE_LIMIT_RPM) + 50.0

    def test_both_overrides_applied(self):
        mod = self._mod
        mod.RATE_LIMIT_OVERRIDES = {"oidc:vip": {"rpm": 300, "burst": 100}}
        max_tokens, refill_rate, rpm = mod._get_user_limits("oidc:vip")
        assert rpm == 300.0
        assert max_tokens == 400.0
        assert refill_rate == 300.0 / 60.0

    def test_override_does_not_affect_other_users(self):
        mod = self._mod
        mod.RATE_LIMIT_OVERRIDES = {"token:special": {"rpm": 1000}}
        _, _, rpm_special = mod._get_user_limits("token:special")
        _, _, rpm_normal = mod._get_user_limits("token:normal")
        assert rpm_special == 1000.0
        assert rpm_normal == float(mod.RATE_LIMIT_RPM)


# ---------------------------------------------------------------------------
# Middleware integration tests with overrides
# ---------------------------------------------------------------------------


class TestRateLimitMiddlewareOverrides:
    """Tests for rate_limit_middleware with per-user overrides."""

    @pytest.fixture(autouse=True)
    def _clear_and_set(self):
        import importlib

        mod = importlib.import_module("middleware.rate_limit_middleware")
        mod._buckets.clear()
        self._mod = mod
        self._original_overrides = mod.RATE_LIMIT_OVERRIDES.copy()
        yield
        mod._buckets.clear()
        mod.RATE_LIMIT_OVERRIDES = self._original_overrides

    @pytest.mark.asyncio
    async def test_higher_override_allows_more_requests(self):
        """A user with a higher RPM override should be able to make more requests."""
        mod = self._mod
        system_max = int(mod._get_max_tokens())  # system default bucket size

        # Give this token a much higher limit
        mod.RATE_LIMIT_OVERRIDES = {"token:vip-token": {"rpm": system_max * 2, "burst": 0}}
        higher_max = system_max * 2

        request = _make_request()
        request.state.authenticated = True
        request.state.api_token_info = {"tokenUUID": "vip-token", "username": "vip"}

        # Should be able to make more requests than the system default
        for i in range(higher_max):
            resp = await mod.rate_limit_middleware(request, _call_next_ok)
            assert resp.status_code == 200, f"Failed at request {i + 1} of {higher_max}"

        # Now should be throttled
        resp = await mod.rate_limit_middleware(request, _call_next_ok)
        assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_lower_override_throttles_sooner(self):
        """A user with a lower RPM override should be throttled sooner."""
        mod = self._mod
        mod.RATE_LIMIT_OVERRIDES = {"token:restricted": {"rpm": 3, "burst": 0}}

        request = _make_request()
        request.state.authenticated = True
        request.state.api_token_info = {"tokenUUID": "restricted", "username": "r"}

        # Should allow exactly 3 requests (rpm=3, burst=0 → max_tokens=3)
        for _ in range(3):
            resp = await mod.rate_limit_middleware(request, _call_next_ok)
            assert resp.status_code == 200

        resp = await mod.rate_limit_middleware(request, _call_next_ok)
        assert resp.status_code == 429

    @pytest.mark.asyncio
    async def test_override_only_affects_targeted_user(self):
        """Override for one user should not change limits for another."""
        mod = self._mod
        mod.RATE_LIMIT_OVERRIDES = {"token:restricted": {"rpm": 2, "burst": 0}}

        # Restricted user
        req_restricted = _make_request()
        req_restricted.state.authenticated = True
        req_restricted.state.api_token_info = {"tokenUUID": "restricted", "username": "r"}

        for _ in range(2):
            await mod.rate_limit_middleware(req_restricted, _call_next_ok)
        resp = await mod.rate_limit_middleware(req_restricted, _call_next_ok)
        assert resp.status_code == 429

        # Normal user should still have the full system default
        req_normal = _make_request()
        req_normal.state.authenticated = True
        req_normal.state.api_token_info = {"tokenUUID": "normal-user", "username": "n"}

        system_max = int(mod._get_max_tokens())
        for _ in range(system_max):
            resp = await mod.rate_limit_middleware(req_normal, _call_next_ok)
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_oidc_user_override(self):
        """OIDC users can also have overrides keyed on oidc:<sub>."""
        mod = self._mod
        mod.RATE_LIMIT_OVERRIDES = {"oidc:power-user": {"rpm": 5, "burst": 0}}

        request = _make_request()
        request.state.authenticated = True
        request.state.jwt_data = {"sub": "power-user"}

        for _ in range(5):
            resp = await mod.rate_limit_middleware(request, _call_next_ok)
            assert resp.status_code == 200

        resp = await mod.rate_limit_middleware(request, _call_next_ok)
        assert resp.status_code == 429
