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

"""
Refactored auth tests using fixture-based mocking instead of global mocks.
This replaces the original test_auth.py with isolated, maintainable tests.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from conftest import LambdaTestHelper


# Set up test environment variables
@pytest.fixture(autouse=True)
def setup_test_env():
    """Set up test environment variables."""
    env_vars = {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing", 
        "AWS_SECURITY_TOKEN": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "ADMIN_GROUP": "admin"  # Default admin group for tests
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
    
    yield
    
    # Cleanup
    for key in env_vars.keys():
        if key in os.environ:
            del os.environ[key]


@pytest.fixture
def auth_module():
    """Import auth module."""
    from utilities import auth
    return auth


@pytest.fixture
def mock_auth_logging():
    """Mock auth module logging."""
    with patch('utilities.auth.logger') as mock_logger:
        yield mock_logger


@pytest.fixture
def sample_event_with_username():
    """Create a sample event with username in requestContext."""
    return {
        "requestContext": {
            "authorizer": {
                "username": "test-user", 
                "groups": '["group1", "group2"]'
            }
        }
    }


@pytest.fixture
def sample_event_without_username():
    """Create a sample event without username in requestContext."""
    return {
        "requestContext": {
            "authorizer": {
                "groups": '["group1", "group2"]'
            }
        }
    }


@pytest.fixture
def sample_event_empty_context():
    """Create a sample event with empty requestContext."""
    return {"requestContext": {}}


@pytest.fixture
def sample_event_no_context():
    """Create a sample event without requestContext."""
    return {}


@pytest.fixture
def admin_event():
    """Create a sample event for admin user."""
    return {
        "requestContext": {
            "authorizer": {
                "username": "admin-user",
                "groups": '["admin", "users"]'
            }
        }
    }


@pytest.fixture
def regular_user_event():
    """Create a sample event for regular user."""
    return {
        "requestContext": {
            "authorizer": {
                "username": "regular-user",
                "groups": '["users"]'
            }
        }
    }


class TestGetUsername:
    """Test get_username function - REFACTORED VERSION."""

    def test_get_username_with_valid_username(self, sample_event_with_username, auth_module):
        """Test getting username when username is present in event."""
        username = auth_module.get_username(sample_event_with_username)
        assert username == "test-user"

    def test_get_username_without_username(self, sample_event_without_username, auth_module):
        """Test getting username when username is not present in event."""
        username = auth_module.get_username(sample_event_without_username)
        assert username == "system"

    def test_get_username_empty_context(self, sample_event_empty_context, auth_module):
        """Test getting username when requestContext is empty."""
        username = auth_module.get_username(sample_event_empty_context)
        assert username == "system"

    def test_get_username_no_context(self, sample_event_no_context, auth_module):
        """Test getting username when requestContext is missing."""
        username = auth_module.get_username(sample_event_no_context)
        assert username == "system"

    def test_get_username_nested_missing_authorizer(self, auth_module):
        """Test getting username when authorizer is missing from requestContext."""
        event = {"requestContext": {"other_field": "value"}}
        username = auth_module.get_username(event)
        assert username == "system"


class TestIsAdmin:
    """Test is_admin function - REFACTORED VERSION."""

    def test_is_admin_with_admin_group(self, sample_event_with_username, auth_module):
        """Test is_admin when user has admin group."""
        with patch("utilities.auth.get_groups", return_value=["group1", "admin", "group2"]):
            result = auth_module.is_admin(sample_event_with_username)
            assert result is True

    def test_is_admin_without_admin_group(self, sample_event_with_username, auth_module):
        """Test is_admin when user does not have admin group."""
        with patch("utilities.auth.get_groups", return_value=["group1", "group2"]):
            result = auth_module.is_admin(sample_event_with_username)
            assert result is False

    def test_is_admin_empty_groups(self, sample_event_with_username, auth_module):
        """Test is_admin when user has no groups."""
        with patch("utilities.auth.get_groups", return_value=[]):
            result = auth_module.is_admin(sample_event_with_username)
            assert result is False

    def test_is_admin_empty_admin_group_env(self, sample_event_with_username, auth_module):
        """Test is_admin when ADMIN_GROUP environment variable is empty."""
        with patch.dict(os.environ, {"ADMIN_GROUP": ""}):
            with patch("utilities.auth.get_groups", return_value=["group1", "group2"]):
                result = auth_module.is_admin(sample_event_with_username)
                assert result is False

    def test_is_admin_no_admin_group_env(self, sample_event_with_username, auth_module):
        """Test is_admin when ADMIN_GROUP environment variable is not set."""
        # Temporarily remove ADMIN_GROUP
        with patch.dict(os.environ, {}, clear=False):
            if "ADMIN_GROUP" in os.environ:
                del os.environ["ADMIN_GROUP"]
            
            with patch("utilities.auth.get_groups", return_value=["group1", "group2"]):
                result = auth_module.is_admin(sample_event_with_username)
                assert result is False

    def test_is_admin_logging(self, sample_event_with_username, auth_module, mock_auth_logging):
        """Test is_admin logs the groups and admin group."""
        with patch("utilities.auth.get_groups", return_value=["group1", "admin"]):
            auth_module.is_admin(sample_event_with_username)
            mock_auth_logging.info.assert_called_once_with("User groups: ['group1', 'admin'] and admin: admin")


class TestAdminOnlyDecorator:
    """Test admin_only decorator - REFACTORED VERSION."""

    def test_admin_only_decorator_with_admin_user(self, auth_module, lambda_context):
        """Test admin_only decorator allows admin users to access function."""
        with patch("utilities.auth.is_admin", return_value=True):
            @auth_module.admin_only
            def test_function(event, context):
                return {"result": "success"}

            event = {"test": "data"}
            result = test_function(event, lambda_context)

        assert result == {"result": "success"}

    def test_admin_only_decorator_with_non_admin_user(self, auth_module, lambda_context):
        """Test admin_only decorator raises HTTPException for non-admin users."""
        with patch("utilities.auth.is_admin", return_value=False):
            from utilities.exceptions import HTTPException

            @auth_module.admin_only
            def test_function(event, context):
                return {"result": "success"}

            event = {"test": "data"}

            with pytest.raises(HTTPException) as exc_info:
                test_function(event, lambda_context)

            assert exc_info.value.http_status_code == 403
            assert exc_info.value.message == "User does not have permission to access this repository"

    def test_admin_only_decorator_preserves_function_metadata(self, auth_module):
        """Test admin_only decorator preserves original function metadata."""
        @auth_module.admin_only
        def test_function(event, context):
            """Test function docstring."""
            return {"result": "success"}

        assert test_function.__name__ == "test_function"
        assert test_function.__doc__ == "Test function docstring."

    def test_admin_only_decorator_with_function_args_kwargs(self, auth_module, lambda_context):
        """Test admin_only decorator works with functions that have additional args."""
        with patch("utilities.auth.is_admin", return_value=True):
            @auth_module.admin_only
            def test_function(event, context, *args, **kwargs):
                return {"result": "success", "args": args, "kwargs": kwargs}

            event = {"test": "data"}
            result = test_function(event, lambda_context, "arg1", "arg2", key1="value1")

        assert result["result"] == "success"
        assert result["args"] == ("arg1", "arg2")
        assert result["kwargs"] == {"key1": "value1"}

    def test_admin_only_decorator_function_raises_exception(self, auth_module, lambda_context):
        """Test admin_only decorator handles exceptions from wrapped function."""
        with patch("utilities.auth.is_admin", return_value=True):
            @auth_module.admin_only
            def test_function(event, context):
                raise ValueError("Test error")

            event = {"test": "data"}

            with pytest.raises(ValueError, match="Test error"):
                test_function(event, lambda_context)

    def test_admin_only_decorator_calls_is_admin_with_event(self, auth_module, lambda_context):
        """Test admin_only decorator calls is_admin with the event."""
        with patch("utilities.auth.is_admin") as mock_is_admin:
            mock_is_admin.return_value = True

            @auth_module.admin_only
            def test_function(event, context):
                return {"result": "success"}

            event = {"test": "data"}
            test_function(event, lambda_context)
            mock_is_admin.assert_called_once_with(event)

    def test_admin_only_decorator_with_extra_args(self, auth_module, lambda_context):
        """Test admin_only decorator with additional args and kwargs."""
        with patch("utilities.auth.is_admin", return_value=True):
            @auth_module.admin_only
            def test_function(event, context, extra_arg, extra_kwarg=None):
                return {"result": "success", "extra_arg": extra_arg, "extra_kwarg": extra_kwarg}

            event = {"test": "data"}
            result = test_function(event, lambda_context, "test_arg", extra_kwarg="test_kwarg")

        assert result == {"result": "success", "extra_arg": "test_arg", "extra_kwarg": "test_kwarg"}

    def test_admin_only_decorator_function_exception_propagation(self, auth_module, lambda_context):
        """Test admin_only decorator allows underlying function exceptions to propagate."""
        with patch("utilities.auth.is_admin", return_value=True):
            @auth_module.admin_only
            def test_function(event, context):
                raise ValueError("Function error")

            event = {"test": "data"}

            with pytest.raises(ValueError) as exc_info:
                test_function(event, lambda_context)

            assert str(exc_info.value) == "Function error"

    def test_admin_only_decorator_event_passing(self, auth_module, lambda_context):
        """Test admin_only decorator calls is_admin with the correct event."""
        with patch("utilities.auth.is_admin", return_value=True) as mock_is_admin:
            @auth_module.admin_only
            def test_function(event, context):
                return {"result": "success"}

            event = {"test": "data"}
            test_function(event, lambda_context)

        mock_is_admin.assert_called_once_with(event)


class TestAuthFlow:
    """Test complete authentication flows - REFACTORED VERSION."""

    def test_full_auth_flow_admin_user(self, admin_event, auth_module):
        """Test full authentication flow for admin user."""
        with patch("utilities.auth.get_groups", return_value=["admin", "users"]):
            username = auth_module.get_username(admin_event)
            admin_status = auth_module.is_admin(admin_event)

        assert username == "admin-user"
        assert admin_status is True

    def test_full_auth_flow_regular_user(self, regular_user_event, auth_module):
        """Test full authentication flow for regular user."""
        with patch("utilities.auth.get_groups", return_value=["users"]):
            username = auth_module.get_username(regular_user_event)
            admin_status = auth_module.is_admin(regular_user_event)

        assert username == "regular-user"
        assert admin_status is False

    def test_system_user_auth_flow(self, sample_event_no_context, auth_module):
        """Test authentication flow for system user (no context)."""
        with patch("utilities.auth.get_groups", return_value=[]):
            username = auth_module.get_username(sample_event_no_context)
            admin_status = auth_module.is_admin(sample_event_no_context)

        assert username == "system"
        assert admin_status is False

    def test_complete_auth_flow_admin_user(self, auth_module, lambda_context):
        """Test complete auth flow for an admin user."""
        event = {
            "requestContext": {
                "authorizer": {
                    "username": "admin_user",
                    "groups": '["user", "lisa-admin"]'
                }
            }
        }

        # Test get_username
        username = auth_module.get_username(event)
        assert username == "admin_user"

        # Test is_admin (need to mock get_groups)
        with patch.dict(os.environ, {"ADMIN_GROUP": "lisa-admin"}):
            with patch("utilities.auth.get_groups", return_value=["user", "lisa-admin"]):
                admin_status = auth_module.is_admin(event)
                assert admin_status is True

                # Test admin_only decorator
                @auth_module.admin_only
                def admin_function(event, context):
                    return {"user": auth_module.get_username(event), "admin": True}

                result = admin_function(event, lambda_context)
                assert result == {"user": "admin_user", "admin": True}

    def test_complete_auth_flow_regular_user(self, auth_module, lambda_context):
        """Test complete auth flow for a regular user."""
        event = {
            "requestContext": {
                "authorizer": {
                    "username": "regular_user",
                    "groups": '["user"]'
                }
            }
        }
        
        from utilities.exceptions import HTTPException

        # Test get_username
        username = auth_module.get_username(event)
        assert username == "regular_user"

        # Test is_admin (need to mock get_groups)
        with patch.dict(os.environ, {"ADMIN_GROUP": "lisa-admin"}):
            with patch("utilities.auth.get_groups", return_value=["user"]):
                admin_status = auth_module.is_admin(event)
                assert admin_status is False

                # Test admin_only decorator
                @auth_module.admin_only
                def admin_function(event, context):
                    return {"user": auth_module.get_username(event), "admin": True}

                with pytest.raises(HTTPException) as exc_info:
                    admin_function(event, lambda_context)

                assert exc_info.value.http_status_code == 403

    def test_complete_system_user_auth_flow(self, auth_module, lambda_context):
        """Test auth flow for system user (no context)."""
        event = {}

        # Test get_username
        username = auth_module.get_username(event)
        assert username == "system"

        # Test is_admin with system user
        with patch("utilities.auth.get_groups", return_value=[]):
            admin_status = auth_module.is_admin(event)
            assert admin_status is False


class TestGetUserContext:
    """Test get_user_context function - REFACTORED VERSION."""

    def test_get_user_context_admin_user(self, admin_event, auth_module):
        """Test get_user_context for admin user."""
        with patch.object(auth_module, 'get_username', return_value="admin-user"), \
             patch.object(auth_module, 'is_admin', return_value=True):
            
            username, is_admin_user = auth_module.get_user_context(admin_event)
            
            assert username == "admin-user"
            assert is_admin_user is True

    def test_get_user_context_regular_user(self, regular_user_event, auth_module):
        """Test get_user_context for regular user."""
        with patch.object(auth_module, 'get_username', return_value="regular-user"), \
             patch.object(auth_module, 'is_admin', return_value=False):
            
            username, is_admin_user = auth_module.get_user_context(regular_user_event)
            
            assert username == "regular-user"
            assert is_admin_user is False

    def test_get_user_context_system_user(self, sample_event_no_context, auth_module):
        """Test get_user_context for system user."""
        with patch.object(auth_module, 'get_username', return_value="system"), \
             patch.object(auth_module, 'is_admin', return_value=False):
            
            username, is_admin_user = auth_module.get_user_context(sample_event_no_context)
            
            assert username == "system"
            assert is_admin_user is False
