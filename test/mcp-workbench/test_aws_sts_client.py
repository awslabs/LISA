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

from datetime import datetime, timedelta, timezone
from typing import Any

import boto3
import pytest
from mcpworkbench.aws.session_models import AwsSessionRecord
from mcpworkbench.aws.sts_client import AwsStsClient, InvalidAwsCredentialsError


class _FakeStsClient:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail

    def get_caller_identity(self) -> dict[str, Any]:
        if self.should_fail:
            raise Exception("AccessDenied")
        return {
            "Account": "123456789012",
            "Arn": "arn:aws:iam::123456789012:user/test-user",
            "UserId": "AIDAEXAMPLE",
        }

    def get_session_token(self, DurationSeconds: int) -> dict[str, Any]:  # noqa: N803
        if self.should_fail:
            raise Exception("STS failure")
        expiration = datetime.now(timezone.utc) + timedelta(seconds=DurationSeconds)
        return {
            "Credentials": {
                "AccessKeyId": "ASIA_TEMP",
                "SecretAccessKey": "temp-secret",
                "SessionToken": "temp-token",
                "Expiration": expiration,
            }
        }


def test_validate_static_credentials_returns_account_and_arn(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_client(service_name: str, **_: Any) -> _FakeStsClient:
        assert service_name == "sts"
        return _FakeStsClient()

    monkeypatch.setattr(boto3, "client", _fake_client)

    client = AwsStsClient()
    account_id, arn = client.validate_static_credentials(
        access_key_id="AKIA_TEST",
        secret_access_key="secret",
        session_token=None,
        region="us-east-1",
    )

    assert account_id == "123456789012"
    assert arn == "arn:aws:iam::123456789012:user/test-user"


def test_validate_static_credentials_raises_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_client(service_name: str, **_: Any) -> _FakeStsClient:
        assert service_name == "sts"
        return _FakeStsClient(should_fail=True)

    monkeypatch.setattr(boto3, "client", _fake_client)

    client = AwsStsClient()

    with pytest.raises(InvalidAwsCredentialsError):
        client.validate_static_credentials(
            access_key_id="AKIA_TEST",
            secret_access_key="secret",
            session_token=None,
            region="us-east-1",
        )


def test_create_session_credentials_returns_aws_session_record(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_client(service_name: str, **_: Any) -> _FakeStsClient:
        assert service_name == "sts"
        return _FakeStsClient()

    monkeypatch.setattr(boto3, "client", _fake_client)

    client = AwsStsClient()

    record: AwsSessionRecord = client.create_session_credentials(
        user_id="user-1",
        session_id="session-1",
        access_key_id="AKIA_TEST",
        secret_access_key="secret",
        session_token=None,
        region="us-east-1",
        duration_seconds=3600,
        safety_margin_seconds=60,
    )

    assert record.user_id == "user-1"
    assert record.session_id == "session-1"
    assert record.aws_region == "us-east-1"
    assert record.aws_access_key_id == "ASIA_TEMP"
    assert record.aws_secret_access_key == "temp-secret"
    assert record.aws_session_token == "temp-token"
    # expires_at should be strictly before the raw STS Expiration because of safety margin
    now = datetime.now(timezone.utc)
    assert record.expires_at > now
