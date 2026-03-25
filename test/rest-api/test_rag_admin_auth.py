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

"""Tests for RAG admin authorization in REST API auth provider and middleware."""
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add the REST API source to the path
rest_api_src = Path(__file__).parent.parent.parent / "lib" / "serve" / "rest-api" / "src"
sys.path.insert(0, str(rest_api_src))


class TestCheckRagAdminAccess:
    """Tests for OIDCAuthorizationProvider.check_rag_admin_access (groups-based)."""

    def test_returns_true_when_in_group(self):
        from auth_provider import OIDCAuthorizationProvider

        with patch.dict(os.environ, {"RAG_ADMIN_GROUP": "rag-admin"}):
            provider = OIDCAuthorizationProvider(admin_group="admin", user_group="users")
            assert provider.check_rag_admin_access("testuser", ["rag-admin", "users"]) is True

    def test_returns_false_when_not_in_group(self):
        from auth_provider import OIDCAuthorizationProvider

        with patch.dict(os.environ, {"RAG_ADMIN_GROUP": "rag-admin"}):
            provider = OIDCAuthorizationProvider(admin_group="admin", user_group="users")
            assert provider.check_rag_admin_access("testuser", ["users", "developers"]) is False

    def test_returns_false_when_no_groups(self):
        from auth_provider import OIDCAuthorizationProvider

        with patch.dict(os.environ, {"RAG_ADMIN_GROUP": "rag-admin"}):
            provider = OIDCAuthorizationProvider(admin_group="admin", user_group="users")
            assert provider.check_rag_admin_access("testuser", None) is False
            assert provider.check_rag_admin_access("testuser", []) is False

    def test_returns_false_when_env_var_empty(self):
        from auth_provider import OIDCAuthorizationProvider

        with patch.dict(os.environ, {"RAG_ADMIN_GROUP": ""}):
            provider = OIDCAuthorizationProvider(admin_group="admin", user_group="users")
            assert provider.check_rag_admin_access("testuser", ["rag-admin", "users"]) is False


class TestCheckRagAdminAccessJwt:
    """Tests for OIDCAuthorizationProvider.check_rag_admin_access_jwt (JWT-based)."""

    def test_extracts_groups_correctly(self):
        from auth_provider import OIDCAuthorizationProvider

        with patch.dict(os.environ, {"RAG_ADMIN_GROUP": "rag-admin"}):
            provider = OIDCAuthorizationProvider(admin_group="admin", user_group="users")
            jwt_data = {"cognito:groups": ["rag-admin", "users"]}
            assert provider.check_rag_admin_access_jwt(jwt_data, "cognito:groups") is True

    def test_returns_false_when_not_in_group(self):
        from auth_provider import OIDCAuthorizationProvider

        with patch.dict(os.environ, {"RAG_ADMIN_GROUP": "rag-admin"}):
            provider = OIDCAuthorizationProvider(admin_group="admin", user_group="users")
            jwt_data = {"cognito:groups": ["users", "developers"]}
            assert provider.check_rag_admin_access_jwt(jwt_data, "cognito:groups") is False

    def test_returns_false_when_env_var_empty(self):
        from auth_provider import OIDCAuthorizationProvider

        with patch.dict(os.environ, {"RAG_ADMIN_GROUP": ""}):
            provider = OIDCAuthorizationProvider(admin_group="admin", user_group="users")
            jwt_data = {"cognito:groups": ["rag-admin", "users"]}
            assert provider.check_rag_admin_access_jwt(jwt_data, "cognito:groups") is False


class TestMiddlewareIsRagAdmin:
    """Tests for auth_middleware setting request.state.is_rag_admin."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("in_group,expected", [(True, True), (False, False)])
    async def test_sets_is_rag_admin_for_jwt_user(
        self, in_group, expected, mock_env_vars, mock_rag_admin_jwt_data, mock_jwt_data
    ):
        from middleware.auth_middleware import auth_middleware

        jwt_data = mock_rag_admin_jwt_data if in_group else mock_jwt_data

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"

        class State:
            pass

        mock_request.state = State()
        mock_response = MagicMock(status_code=200)

        async def mock_call_next(request):
            return mock_response

        with (
            patch.dict(os.environ, {"USE_AUTH": "true", "RAG_ADMIN_GROUP": "rag-admin"}),
            patch("middleware.auth_middleware.Authorizer") as MockAuthorizer,
        ):
            authorizer_instance = MockAuthorizer.return_value
            authorizer_instance.authenticate_request = AsyncMock(return_value=jwt_data)
            authorizer_instance.jwt_groups_property = "cognito:groups"
            authorizer_instance.auth_provider = MagicMock()
            authorizer_instance.auth_provider.check_admin_access_jwt.return_value = False
            authorizer_instance.auth_provider.check_rag_admin_access_jwt.return_value = in_group

            await auth_middleware(mock_request, mock_call_next)

            assert mock_request.state.is_rag_admin is expected
            authorizer_instance.auth_provider.check_rag_admin_access_jwt.assert_called_once_with(
                jwt_data, "cognito:groups"
            )

    @pytest.mark.asyncio
    async def test_sets_is_rag_admin_true_for_management_token(self, mock_env_vars):
        from middleware.auth_middleware import auth_middleware

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"

        class State:
            pass

        mock_request.state = State()
        mock_response = MagicMock(status_code=200)

        async def mock_call_next(request):
            return mock_response

        with (
            patch.dict(os.environ, {"USE_AUTH": "true"}),
            patch("middleware.auth_middleware.Authorizer") as MockAuthorizer,
        ):
            authorizer_instance = MockAuthorizer.return_value
            # Management token: authenticate_request returns None, no api_token_info
            authorizer_instance.authenticate_request = AsyncMock(return_value=None)

            await auth_middleware(mock_request, mock_call_next)

            assert mock_request.state.is_rag_admin is True

    @pytest.mark.asyncio
    async def test_sets_is_rag_admin_true_for_api_token_in_group(self, mock_env_vars, mock_rag_admin_token_info):
        from middleware.auth_middleware import auth_middleware

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"

        class State:
            pass

        mock_request.state = State()
        mock_request.state.api_token_info = mock_rag_admin_token_info
        mock_response = MagicMock(status_code=200)

        async def mock_call_next(request):
            return mock_response

        with (
            patch.dict(os.environ, {"USE_AUTH": "true", "RAG_ADMIN_GROUP": "rag-admin"}),
            patch("middleware.auth_middleware.Authorizer") as MockAuthorizer,
        ):
            authorizer_instance = MockAuthorizer.return_value
            # API token: authenticate_request returns None, but api_token_info exists
            authorizer_instance.authenticate_request = AsyncMock(return_value=None)
            authorizer_instance.auth_provider = MagicMock()
            authorizer_instance.auth_provider.check_admin_access.return_value = False
            authorizer_instance.auth_provider.check_rag_admin_access.return_value = True

            await auth_middleware(mock_request, mock_call_next)

            assert mock_request.state.is_rag_admin is True
            authorizer_instance.auth_provider.check_rag_admin_access.assert_called_once_with(
                "api-rag-admin", ["rag-admin", "users"]
            )

    @pytest.mark.asyncio
    async def test_sets_is_rag_admin_true_when_auth_disabled(self, mock_env_vars):
        from middleware.auth_middleware import auth_middleware

        mock_request = MagicMock()
        mock_request.method = "GET"
        mock_request.url.path = "/test"

        class State:
            pass

        mock_request.state = State()
        mock_response = MagicMock(status_code=200)

        async def mock_call_next(request):
            return mock_response

        with patch.dict(os.environ, {"USE_AUTH": "false"}):
            await auth_middleware(mock_request, mock_call_next)

            assert mock_request.state.is_rag_admin is True
