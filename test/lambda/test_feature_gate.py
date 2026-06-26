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

"""Unit tests for the server-side feature gate utility.

Covers ``is_feature_enabled``, the ``require_feature`` decorator for traditional
Lambda handlers, the 5-minute TTL cache, and the fail-open behavior when the
config table is unreachable or unset.
"""

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("CONFIG_TABLE_NAME", "config-table")

from lisa.utilities.exceptions import ForbiddenException
from lisa.utilities.feature_gate import (
    _feature_cache,
    _get_enabled_components,
    is_feature_enabled,
    require_feature,
)


@pytest.fixture(autouse=True)
def clear_feature_cache():
    """The TTL cache is process-global; clear it around every test so cases
    don't leak cached config into one another."""
    _feature_cache.clear()
    yield
    _feature_cache.clear()


def _mock_config_table(enabled_components):
    """Build a mock DynamoDB Table whose query returns a single global config
    item carrying the given enabledComponents dict."""
    table = MagicMock()
    table.query.return_value = {
        "Items": [{"configScope": "global", "versionId": 0, "configuration": {"enabledComponents": enabled_components}}]
    }
    return table


# ---------------------------------------------------------------------------
# is_feature_enabled
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "components,feature_key,expected",
    [
        ({"deleteSessionHistory": True}, "deleteSessionHistory", True),
        ({"deleteSessionHistory": False}, "deleteSessionHistory", False),
        # Missing key -> fail-open (enabled). A toggle absent from config must
        # not silently disable an existing capability.
        ({"someOtherToggle": False}, "deleteSessionHistory", True),
        ({}, "deleteSessionHistory", True),
    ],
)
def test_is_feature_enabled_reads_config(components, feature_key, expected):
    with patch("lisa.utilities.feature_gate._get_config_table", return_value=_mock_config_table(components)):
        assert is_feature_enabled(feature_key) is expected


def test_is_feature_enabled_no_global_item_fails_open():
    """When no global configuration row exists yet, features default to enabled."""
    table = MagicMock()
    table.query.return_value = {"Items": []}
    with patch("lisa.utilities.feature_gate._get_config_table", return_value=table):
        assert is_feature_enabled("deleteSessionHistory") is True


def test_is_feature_enabled_no_table_name_fails_open():
    """Missing CONFIG_TABLE_NAME must fail open, not crash the handler."""
    with patch("lisa.utilities.feature_gate._get_config_table", return_value=None):
        assert is_feature_enabled("deleteSessionHistory") is True


def test_is_feature_enabled_ddb_error_fails_open():
    """A DynamoDB error must fail open (availability over security; the
    authorizer has already validated auth)."""
    table = MagicMock()
    table.query.side_effect = Exception("DynamoDB unavailable")
    with patch("lisa.utilities.feature_gate._get_config_table", return_value=table):
        assert is_feature_enabled("deleteSessionHistory") is True


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------


def test_enabled_components_cached_across_calls():
    """The full enabledComponents dict is cached so repeated checks within the
    TTL window don't hammer the config table."""
    table = _mock_config_table({"deleteSessionHistory": False, "uploadRagDocs": True})
    with patch("lisa.utilities.feature_gate._get_config_table", return_value=table):
        # Two different toggles, several lookups — should hit DDB exactly once.
        assert is_feature_enabled("deleteSessionHistory") is False
        assert is_feature_enabled("uploadRagDocs") is True
        assert is_feature_enabled("deleteSessionHistory") is False
    assert table.query.call_count == 1


def test_cache_refreshes_after_clear():
    """A fresh read after cache expiry/clear reflects updated config."""
    first = _mock_config_table({"deleteSessionHistory": True})
    with patch("lisa.utilities.feature_gate._get_config_table", return_value=first):
        assert is_feature_enabled("deleteSessionHistory") is True

    _feature_cache.clear()  # simulate TTL expiry

    second = _mock_config_table({"deleteSessionHistory": False})
    with patch("lisa.utilities.feature_gate._get_config_table", return_value=second):
        assert is_feature_enabled("deleteSessionHistory") is False


def test_get_enabled_components_queries_latest_global_version():
    """The query must select the global scope, newest version first, limit 1."""
    table = _mock_config_table({"deleteSessionHistory": True})
    with patch("lisa.utilities.feature_gate._get_config_table", return_value=table):
        _get_enabled_components()
    _, kwargs = table.query.call_args
    assert kwargs["ScanIndexForward"] is False
    assert kwargs["Limit"] == 1
    assert kwargs["ExpressionAttributeValues"] == {":scope": "global"}


# ---------------------------------------------------------------------------
# require_feature decorator (traditional Lambda handlers)
# ---------------------------------------------------------------------------


def test_require_feature_allows_when_enabled():
    @require_feature("deleteSessionHistory")
    def handler(event, context):
        return {"ok": True}

    with patch(
        "lisa.utilities.feature_gate._get_config_table", return_value=_mock_config_table({"deleteSessionHistory": True})
    ):
        assert handler({}, {}) == {"ok": True}


def test_require_feature_rejects_when_disabled():
    @require_feature("deleteSessionHistory")
    def handler(event, context):
        return {"ok": True}

    with patch(
        "lisa.utilities.feature_gate._get_config_table",
        return_value=_mock_config_table({"deleteSessionHistory": False}),
    ):
        with pytest.raises(ForbiddenException) as exc_info:
            handler({}, {})
    assert exc_info.value.http_status_code == 403
    assert "deleteSessionHistory" in exc_info.value.message


def test_require_feature_does_not_invoke_handler_when_disabled():
    """A disabled gate must short-circuit before the wrapped handler runs."""
    handler_body = MagicMock(return_value={"ok": True})

    @require_feature("deleteSessionHistory")
    def handler(event, context):
        return handler_body(event, context)

    with patch(
        "lisa.utilities.feature_gate._get_config_table",
        return_value=_mock_config_table({"deleteSessionHistory": False}),
    ):
        with pytest.raises(ForbiddenException):
            handler({}, {})
    handler_body.assert_not_called()


def test_require_feature_passes_through_args_and_context():
    captured = {}

    @require_feature("deleteSessionHistory")
    def handler(event, context):
        captured["event"] = event
        captured["context"] = context
        return {"ok": True}

    event = {"requestContext": {"authorizer": {"username": "alice"}}}
    context = {"aws_request_id": "abc"}
    with patch(
        "lisa.utilities.feature_gate._get_config_table", return_value=_mock_config_table({"deleteSessionHistory": True})
    ):
        handler(event, context)
    assert captured["event"] is event
    assert captured["context"] is context


def test_require_feature_preserves_function_metadata():
    @require_feature("deleteSessionHistory")
    def my_handler(event, context):
        """Original docstring."""
        return {}

    assert my_handler.__name__ == "my_handler"
    assert my_handler.__doc__ == "Original docstring."
