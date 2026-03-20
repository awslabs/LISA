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

import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("MANAGEMENT_KEY_SECRET_NAME_PS", "/test/management-key")


@pytest.fixture
def lambda_context():
    return SimpleNamespace(
        function_name="test_function",
        function_version="$LATEST",
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test_function",
        memory_limit_in_mb=128,
        aws_request_id="test-request-id",
        log_group_name="/aws/lambda/test_function",
        log_stream_name="2024/03/27/[$LATEST]test123",
    )


@pytest.fixture(autouse=True)
def clear_modules():
    for mod in list(sys.modules):
        if "utilities.auth" in mod:
            del sys.modules[mod]
    yield
    for mod in list(sys.modules):
        if "utilities.auth" in mod:
            del sys.modules[mod]


# --- AuthorizationProvider tests ---


def test_check_rag_admin_access_returns_true_when_in_group():
    with patch.dict(os.environ, {"RAG_ADMIN_GROUP": "rag-admins"}):
        from utilities.auth_provider import OIDCAuthorizationProvider

        provider = OIDCAuthorizationProvider()
        assert provider.check_rag_admin_access("user1", ["rag-admins", "users"]) is True


def test_check_rag_admin_access_returns_false_when_not_in_group():
    with patch.dict(os.environ, {"RAG_ADMIN_GROUP": "rag-admins"}):
        from utilities.auth_provider import OIDCAuthorizationProvider

        provider = OIDCAuthorizationProvider()
        assert provider.check_rag_admin_access("user1", ["users"]) is False


def test_check_rag_admin_access_returns_false_when_groups_empty():
    with patch.dict(os.environ, {"RAG_ADMIN_GROUP": "rag-admins"}):
        from utilities.auth_provider import OIDCAuthorizationProvider

        provider = OIDCAuthorizationProvider()
        assert provider.check_rag_admin_access("user1", []) is False


def test_check_rag_admin_access_returns_false_when_env_var_empty():
    with patch.dict(os.environ, {"RAG_ADMIN_GROUP": ""}):
        from utilities.auth_provider import OIDCAuthorizationProvider

        provider = OIDCAuthorizationProvider()
        assert provider.check_rag_admin_access("user1", ["rag-admins"]) is False


def test_check_rag_admin_access_is_case_sensitive():
    with patch.dict(os.environ, {"RAG_ADMIN_GROUP": "RAG-Admins"}):
        from utilities.auth_provider import OIDCAuthorizationProvider

        provider = OIDCAuthorizationProvider()
        assert provider.check_rag_admin_access("user1", ["rag-admins"]) is False
        assert provider.check_rag_admin_access("user1", ["RAG-Admins"]) is True


# --- is_rag_admin tests ---


def test_is_rag_admin_extracts_from_event_context():
    event = {"requestContext": {"authorizer": {"username": "rag-user", "groups": '["rag-admins", "users"]'}}}
    with patch.dict(os.environ, {"RAG_ADMIN_GROUP": "rag-admins"}):
        with patch("utilities.auth.get_groups", return_value=["rag-admins", "users"]):
            from utilities.auth import is_rag_admin

            assert is_rag_admin(event) is True


# --- rag_admin_or_admin decorator tests ---


def test_rag_admin_or_admin_allows_admin(lambda_context):
    with patch("utilities.auth.is_admin", return_value=True):
        with patch("utilities.auth.is_rag_admin", return_value=False):
            from utilities.auth import rag_admin_or_admin

            @rag_admin_or_admin
            def test_func(event, context):
                return {"result": "success"}

            assert test_func({}, lambda_context) == {"result": "success"}


def test_rag_admin_or_admin_allows_rag_admin(lambda_context):
    with patch("utilities.auth.is_admin", return_value=False):
        with patch("utilities.auth.is_rag_admin", return_value=True):
            from utilities.auth import rag_admin_or_admin

            @rag_admin_or_admin
            def test_func(event, context):
                return {"result": "success"}

            assert test_func({}, lambda_context) == {"result": "success"}


def test_rag_admin_or_admin_blocks_regular_user(lambda_context):
    with patch("utilities.auth.is_admin", return_value=False):
        with patch("utilities.auth.is_rag_admin", return_value=False):
            from utilities.auth import rag_admin_or_admin
            from utilities.exceptions import HTTPException

            @rag_admin_or_admin
            def test_func(event, context):
                return {"result": "success"}

            with pytest.raises(HTTPException) as exc_info:
                test_func({}, lambda_context)

            assert exc_info.value.http_status_code == 403


def test_rag_admin_or_admin_blocks_when_no_groups(lambda_context):
    event = {"requestContext": {"authorizer": {"username": "user1", "groups": "[]"}}}
    with patch.dict(os.environ, {"ADMIN_GROUP": "admin", "RAG_ADMIN_GROUP": "rag-admins"}):
        with patch("utilities.auth.get_groups", return_value=[]):
            from utilities.auth import rag_admin_or_admin
            from utilities.exceptions import HTTPException

            @rag_admin_or_admin
            def test_func(event, context):
                return {"result": "success"}

            with pytest.raises(HTTPException) as exc_info:
                test_func(event, lambda_context)

            assert exc_info.value.http_status_code == 403
