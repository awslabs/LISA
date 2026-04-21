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

from datetime import datetime, timedelta, timezone

import pytest
from mcpworkbench.aws.session_models import AwsSessionRecord
from mcpworkbench.aws.session_service import (
    AwsSessionMissingError,
    AwsSessionService,
)
from mcpworkbench.aws.session_store import InMemoryAwsSessionStore


def _make_record(expires_in_seconds: int = 300) -> AwsSessionRecord:
    now = datetime.now(timezone.utc)
    return AwsSessionRecord(
        user_id="user-1",
        session_id="session-1",
        aws_access_key_id="ASIA_TEMP",
        aws_secret_access_key="temp-secret",
        aws_session_token="temp-token",
        aws_region="us-east-1",
        expires_at=now + timedelta(seconds=expires_in_seconds),
    )


def test_get_aws_session_for_user_returns_record_when_present() -> None:
    store = InMemoryAwsSessionStore()
    record = _make_record()
    store.set_session(record)
    service = AwsSessionService(store=store)

    fetched = service.get_aws_session_for_user("user-1", "session-1")
    assert fetched.user_id == "user-1"
    assert fetched.session_id == "session-1"


def test_get_aws_session_for_user_raises_when_missing() -> None:
    store = InMemoryAwsSessionStore()
    service = AwsSessionService(store=store)

    with pytest.raises(AwsSessionMissingError):
        service.get_aws_session_for_user("user-1", "session-1")


def test_get_aws_session_for_user_raises_when_expired() -> None:
    store = InMemoryAwsSessionStore(safety_margin_seconds=0)
    record = _make_record(expires_in_seconds=-10)
    store.set_session(record)
    service = AwsSessionService(store=store)

    with pytest.raises(AwsSessionMissingError):
        service.get_aws_session_for_user("user-1", "session-1")
