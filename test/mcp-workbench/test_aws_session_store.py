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

import pytest
from mcpworkbench.aws.session_models import AwsSessionRecord
from mcpworkbench.aws.session_store import InMemoryAwsSessionStore


def _make_record(
    user_id: str = "user-1",
    session_id: str = "session-1",
    expires_in_seconds: int = 300,
) -> AwsSessionRecord:
    """Helper to construct a minimal AwsSessionRecord for tests."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=expires_in_seconds)
    return AwsSessionRecord(
        user_id=user_id,
        session_id=session_id,
        aws_access_key_id="AKIA_TEST",
        aws_secret_access_key="secret",
        aws_session_token="token",
        aws_region="us-east-1",
        expires_at=expires_at,
    )


def test_set_and_get_session_returns_same_record() -> None:
    store = InMemoryAwsSessionStore()
    record = _make_record()

    store.set_session(record)

    fetched = store.get_session(record.user_id, record.session_id)
    assert fetched is not None
    assert fetched.user_id == record.user_id
    assert fetched.session_id == record.session_id
    assert fetched.aws_access_key_id == record.aws_access_key_id
    assert fetched.aws_region == record.aws_region


def test_get_session_returns_none_for_unknown_user_or_session() -> None:
    store = InMemoryAwsSessionStore()
    record = _make_record()
    store.set_session(record)

    assert store.get_session("unknown-user", record.session_id) is None
    assert store.get_session(record.user_id, "unknown-session") is None


def test_delete_session_removes_record() -> None:
    store = InMemoryAwsSessionStore()
    record = _make_record()
    store.set_session(record)

    store.delete_session(record.user_id, record.session_id)

    assert store.get_session(record.user_id, record.session_id) is None


def test_get_session_respects_expiration() -> None:
    store = InMemoryAwsSessionStore()
    # Expired 10 seconds ago
    expired_record = _make_record(expires_in_seconds=-10)
    store.set_session(expired_record)

    fetched = store.get_session(expired_record.user_id, expired_record.session_id)
    assert fetched is None


@pytest.mark.parametrize("safety_margin_seconds", [0, 30])
def test_get_session_treats_near_expiration_as_expired(safety_margin_seconds: int) -> None:
    """Ensure that sessions very close to expiration are treated as expired.

    This gives us a small safety buffer so MCP tools don't start long-running operations with credentials that are about
    to expire.
    """
    store = InMemoryAwsSessionStore(safety_margin_seconds=safety_margin_seconds)
    # Expires in 10 seconds; with a 30 second safety margin this should be expired.
    record = _make_record(expires_in_seconds=10)
    store.set_session(record)

    fetched = store.get_session(record.user_id, record.session_id)

    if safety_margin_seconds == 0:
        assert fetched is not None
    else:
        assert fetched is None
