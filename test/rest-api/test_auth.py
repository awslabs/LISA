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

"""Unit tests for REST API authentication."""

import sys
from pathlib import Path
from unittest.mock import patch

# Add REST API src to path
rest_api_src = Path(__file__).parent.parent.parent / "lib" / "serve" / "rest-api" / "src"
sys.path.insert(0, str(rest_api_src))


class TestAuthHeaders:
    """Test suite for AuthHeaders enum."""

    def test_auth_headers_values(self):
        """Test AuthHeaders enum values."""
        # Import inside test to avoid module-level import issues
        from auth import AuthHeaders

        assert AuthHeaders.AUTHORIZATION == "Authorization"
        assert AuthHeaders.API_KEY == "Api-Key"

    def test_auth_headers_values_method(self):
        """Test AuthHeaders.values() returns all header names."""
        from auth import AuthHeaders

        values = AuthHeaders.values()
        assert "Authorization" in values
        assert "Api-Key" in values
        assert len(values) == 2


class TestGetAuthorizationToken:
    """Test suite for get_authorization_token function."""

    def test_get_token_from_authorization_header(self):
        """Test extracting token from Authorization header."""
        from auth import get_authorization_token

        headers = {"Authorization": "Bearer test-token-123"}
        token = get_authorization_token(headers)
        assert token == "test-token-123"

    def test_get_token_without_bearer_prefix(self):
        """Test extracting token without Bearer prefix."""
        from auth import get_authorization_token

        headers = {"Authorization": "test-token-123"}
        token = get_authorization_token(headers)
        assert token == "test-token-123"

    def test_get_token_from_lowercase_header(self):
        """Test extracting token from lowercase header."""
        from auth import get_authorization_token

        headers = {"authorization": "Bearer test-token-123"}
        token = get_authorization_token(headers)
        assert token == "test-token-123"

    def test_get_token_from_api_key_header(self):
        """Test extracting token from Api-Key header."""
        from auth import AuthHeaders, get_authorization_token

        headers = {"Api-Key": "Bearer test-token-123"}
        token = get_authorization_token(headers, AuthHeaders.API_KEY)
        assert token == "test-token-123"

    def test_get_token_missing_header(self):
        """Test extracting token when header is missing."""
        from auth import get_authorization_token

        headers = {}
        token = get_authorization_token(headers)
        assert token == ""


class TestIsUserInGroup:
    """Test suite for is_user_in_group function."""

    def test_user_in_group_simple(self):
        """Test user is in group with simple property path."""
        from auth import is_user_in_group

        jwt_data = {"groups": ["admin", "users"]}
        assert is_user_in_group(jwt_data, "admin", "groups")
        assert is_user_in_group(jwt_data, "users", "groups")

    def test_user_not_in_group(self):
        """Test user is not in group."""
        from auth import is_user_in_group

        jwt_data = {"groups": ["users"]}
        assert not is_user_in_group(jwt_data, "admin", "groups")

    def test_user_in_group_nested_property(self):
        """Test user is in group with nested property path."""
        from auth import is_user_in_group

        jwt_data = {"cognito": {"groups": ["admin", "users"]}}
        assert is_user_in_group(jwt_data, "admin", "cognito.groups")

    def test_user_in_group_missing_property(self):
        """Test user group check with missing property."""
        from auth import is_user_in_group

        jwt_data = {"other": "value"}
        assert not is_user_in_group(jwt_data, "admin", "groups")

    def test_user_in_group_partial_path(self):
        """Test user group check with partial property path."""
        from auth import is_user_in_group

        jwt_data = {"cognito": {"other": "value"}}
        assert not is_user_in_group(jwt_data, "admin", "cognito.groups")


class TestExtractUserGroupsFromJwt:
    """Test suite for extract_user_groups_from_jwt function."""

    def test_extract_groups_simple_path(self, mock_env_vars):
        """Test extracting groups with simple property path."""
        from auth import extract_user_groups_from_jwt

        jwt_data = {"groups": ["admin", "users", "developers"]}
        mock_env_vars["JWT_GROUPS_PROP"] = "groups"

        with patch.dict("os.environ", mock_env_vars):
            groups = extract_user_groups_from_jwt(jwt_data)

        assert groups == ["admin", "users", "developers"]

    def test_extract_groups_nested_path(self, mock_env_vars):
        """Test extracting groups with nested property path."""
        from auth import extract_user_groups_from_jwt

        jwt_data = {"cognito": {"groups": ["admin", "users"]}}
        mock_env_vars["JWT_GROUPS_PROP"] = "cognito.groups"

        with patch.dict("os.environ", mock_env_vars):
            groups = extract_user_groups_from_jwt(jwt_data)

        assert groups == ["admin", "users"]

    def test_extract_groups_none_jwt_data(self, mock_env_vars):
        """Test extracting groups with None JWT data (API token user)."""
        from auth import extract_user_groups_from_jwt

        with patch.dict("os.environ", mock_env_vars):
            groups = extract_user_groups_from_jwt(None)

        assert groups == []

    def test_extract_groups_missing_property(self, mock_env_vars):
        """Test extracting groups when property doesn't exist."""
        from auth import extract_user_groups_from_jwt

        jwt_data = {"other": "value"}
        mock_env_vars["JWT_GROUPS_PROP"] = "groups"

        with patch.dict("os.environ", mock_env_vars):
            groups = extract_user_groups_from_jwt(jwt_data)

        assert groups == []

    def test_extract_groups_not_a_list(self, mock_env_vars):
        """Test extracting groups when property is not a list."""
        from auth import extract_user_groups_from_jwt

        jwt_data = {"groups": "admin"}
        mock_env_vars["JWT_GROUPS_PROP"] = "groups"

        with patch.dict("os.environ", mock_env_vars):
            groups = extract_user_groups_from_jwt(jwt_data)

        assert groups == []


class TestUserContextHelpers:
    """Test suite for user context helper functions."""

    def test_is_api_user_true(self, mock_request, mock_token_info):
        """Test is_api_user returns True for API token user."""
        from auth import is_api_user

        mock_request.state.api_token_info = mock_token_info
        assert is_api_user(mock_request) is True

    def test_is_api_user_false(self, mock_request):
        """Test is_api_user returns False for non-API token user."""
        from auth import is_api_user

        # Ensure api_token_info attribute doesn't exist
        delattr(mock_request.state, "api_token_info") if hasattr(mock_request.state, "api_token_info") else None
        assert is_api_user(mock_request) is False

    def test_get_user_context_api_user(self, mock_request, mock_token_info):
        """Test get_user_context for API token user."""
        from auth import get_user_context

        mock_request.state.api_token_info = mock_token_info

        username, groups = get_user_context(mock_request)

        assert username == "api-user"
        assert groups == ["users"]

    def test_get_user_context_jwt_user(self, mock_request):
        """Test get_user_context for JWT user."""
        from auth import get_user_context

        # Ensure api_token_info doesn't exist
        if hasattr(mock_request.state, "api_token_info"):
            delattr(mock_request.state, "api_token_info")

        mock_request.state.username = "jwt-user"
        mock_request.state.groups = ["admin", "users"]

        username, groups = get_user_context(mock_request)

        assert username == "jwt-user"
        assert groups == ["admin", "users"]

    def test_get_user_context_unknown_user(self, mock_request):
        """Test get_user_context for unknown user."""
        from auth import get_user_context

        # Ensure api_token_info doesn't exist
        if hasattr(mock_request.state, "api_token_info"):
            delattr(mock_request.state, "api_token_info")

        username, groups = get_user_context(mock_request)

        assert username == "unknown"
        assert groups == []
