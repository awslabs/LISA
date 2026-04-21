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

from __future__ import annotations

import base64
import json

import pytest
from mcpworkbench.aws.identity import (
    _current_identity,
    _extract_identity_from_headers,
    CallerIdentity,
    CallerIdentityError,
    decode_jwt_payload,
    get_caller_identity,
)


def _encode_jwt(claims: dict) -> str:
    """Build a minimal unsigned JWT with the given payload claims."""
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).rstrip(b"=").decode()
    return f"{header}.{payload}.sig"


class TestDecodeJwtPayload:
    def test_extracts_claims(self) -> None:
        token = _encode_jwt({"sub": "user-42", "iss": "test"})
        claims = decode_jwt_payload(token)
        assert claims["sub"] == "user-42"
        assert claims["iss"] == "test"

    def test_returns_empty_for_garbage(self) -> None:
        assert decode_jwt_payload("not-a-jwt") == {}

    def test_returns_empty_for_empty(self) -> None:
        assert decode_jwt_payload("") == {}


class TestExtractIdentityFromHeaders:
    def test_jwt_and_session_id(self) -> None:
        token = _encode_jwt({"sub": "user-abc"})
        headers = {"authorization": f"Bearer {token}", "x-session-id": "sess-123"}
        identity = _extract_identity_from_headers(headers)
        assert identity == CallerIdentity(user_id="user-abc", session_id="sess-123")

    def test_prefers_explicit_user_id_header(self) -> None:
        token = _encode_jwt({"sub": "jwt-user"})
        headers = {
            "authorization": f"Bearer {token}",
            "x-user-id": "explicit-user",
            "x-session-id": "sess-456",
        }
        identity = _extract_identity_from_headers(headers)
        assert identity is not None
        assert identity.user_id == "explicit-user"

    def test_returns_none_when_no_user_id(self) -> None:
        assert _extract_identity_from_headers({"x-session-id": "sess-789"}) is None

    def test_returns_none_when_no_session_id(self) -> None:
        token = _encode_jwt({"sub": "user-abc"})
        assert _extract_identity_from_headers({"authorization": f"Bearer {token}"}) is None

    def test_returns_none_for_empty_headers(self) -> None:
        assert _extract_identity_from_headers({}) is None


class TestGetCallerIdentity:
    def test_returns_identity_from_contextvar(self) -> None:
        identity = CallerIdentity(user_id="u1", session_id="s1")
        token = _current_identity.set(identity)
        try:
            assert get_caller_identity() == identity
        finally:
            _current_identity.reset(token)

    def test_raises_when_contextvar_is_none(self) -> None:
        token = _current_identity.set(None)
        try:
            with pytest.raises(CallerIdentityError):
                get_caller_identity()
        finally:
            _current_identity.reset(token)

    def test_raises_when_contextvar_not_set(self) -> None:
        with pytest.raises(CallerIdentityError):
            get_caller_identity()
