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

import asyncio
import json
from typing import Any

import pytest
from fastapi import HTTPException
from mcpworkbench.aws import aws_routes
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import Scope


def _make_request(path: str, method: str, headers: dict[str, str]) -> Request:
    scope: Scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "headers": [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()],
    }
    return Request(scope)


def _make_request_with_body(path: str, method: str, headers: dict[str, str], body: dict[str, Any]) -> Request:
    """Build a Request with JSON body in the ASGI receive stream."""
    body_bytes = json.dumps(body).encode("utf-8")

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": body_bytes, "more_body": False}

    scope: Scope = {
        "type": "http",
        "http_version": "1.1",
        "method": method,
        "path": path,
        "headers": [(k.lower().encode("latin-1"), v.encode("latin-1")) for k, v in headers.items()],
    }
    return Request(scope, receive)


def _headers() -> dict[str, str]:
    return {
        "X-User-Id": "user-1",
        "X-Session-Id": "session-1",
    }


def test_status_returns_disconnected_when_no_session() -> None:
    request = _make_request("/api/aws/status", "GET", _headers())
    data = asyncio.run(aws_routes.aws_status(request))
    assert data == {"connected": False}


def test_connect_aws_missing_fields_returns_400() -> None:
    body: dict[str, Any] = {"accessKeyId": "AKIA_TEST"}
    request = _make_request_with_body("/api/aws/connect", "POST", _headers(), body)

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(aws_routes.connect_aws(request))
    assert exc_info.value.status_code == 400


def test_connect_and_status_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_validate_static_credentials(*_: Any, **__: Any) -> tuple[str, str]:
        return "123456789012", "arn:aws:iam::123456789012:user/test-user"

    def fake_create_session_credentials(*_: Any, **__: Any):
        from datetime import datetime, timedelta, timezone

        from mcpworkbench.aws.session_models import AwsSessionRecord

        now = datetime.now(timezone.utc)
        return AwsSessionRecord(
            user_id="user-1",
            session_id="session-1",
            aws_access_key_id="ASIA_TEMP",
            aws_secret_access_key="temp-secret",
            aws_session_token="temp-token",
            aws_region="us-east-1",
            expires_at=now + timedelta(minutes=10),
        )

    monkeypatch.setattr(aws_routes._sts_client, "validate_static_credentials", fake_validate_static_credentials)
    monkeypatch.setattr(aws_routes._sts_client, "create_session_credentials", fake_create_session_credentials)

    body = {
        "accessKeyId": "AKIA_TEST",
        "secretAccessKey": "secret",
        "region": "us-east-1",
    }
    connect_request = _make_request_with_body("/api/aws/connect", "POST", _headers(), body)
    connect_data = asyncio.run(aws_routes.connect_aws(connect_request))
    assert connect_data["accountId"] == "123456789012"
    assert connect_data["arn"].startswith("arn:aws:iam::123456789012:")
    assert "expiresAt" in connect_data

    status_request = _make_request("/api/aws/status", "GET", _headers())
    status_data = asyncio.run(aws_routes.aws_status(status_request))
    assert status_data["connected"] is True
    assert "expiresAt" in status_data


def test_disconnect_clears_session(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_validate_static_credentials(*_: Any, **__: Any) -> tuple[str, str]:
        return "123456789012", "arn:aws:iam::123456789012:user/test-user"

    def fake_create_session_credentials(*_: Any, **__: Any):
        from datetime import datetime, timedelta, timezone

        from mcpworkbench.aws.session_models import AwsSessionRecord

        now = datetime.now(timezone.utc)
        return AwsSessionRecord(
            user_id="user-1",
            session_id="session-1",
            aws_access_key_id="ASIA_TEMP",
            aws_secret_access_key="temp-secret",
            aws_session_token="temp-token",
            aws_region="us-east-1",
            expires_at=now + timedelta(minutes=10),
        )

    monkeypatch.setattr(aws_routes._sts_client, "validate_static_credentials", fake_validate_static_credentials)
    monkeypatch.setattr(aws_routes._sts_client, "create_session_credentials", fake_create_session_credentials)

    body = {
        "accessKeyId": "AKIA_TEST",
        "secretAccessKey": "secret",
        "region": "us-east-1",
    }
    connect_request = _make_request_with_body("/api/aws/connect", "POST", _headers(), body)
    asyncio.run(aws_routes.connect_aws(connect_request))

    disconnect_request = _make_request("/api/aws/connect", "DELETE", _headers())
    response: Response = asyncio.run(aws_routes.disconnect_aws(disconnect_request))
    assert response.status_code == 204

    status_request = _make_request("/api/aws/status", "GET", _headers())
    status_data = asyncio.run(aws_routes.aws_status(status_request))
    assert status_data == {"connected": False}
