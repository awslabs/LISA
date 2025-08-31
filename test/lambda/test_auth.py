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

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context."""
    return SimpleNamespace(
        function_name="test_function",
        function_version="$LATEST",
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test_function",
        memory_limit_in_mb=128,
        aws_request_id="test-request-id",
        log_group_name="/aws/lambda/test_function",
        log_stream_name="2024/03/27/[$LATEST]test123",
    )





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
    return {
        "requestContext": {}
    }


@pytest.fixture
def sample_event_no_context():
    """Create a sample event without requestContext."""
    return {}


def test_get_username_with_valid_username(sample_event_with_username):
    """Test getting username when username is present in event."""
    # Clean up any existing modules
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    from utilities.auth import get_username

    username = get_username(sample_event_with_username)
    assert username == "test-user"

def test_get_username_without_username(sample_event_without_username):
    """Test getting username when username is not present in event."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    from utilities.auth import get_username

    username = get_username(sample_event_without_username)
    assert username == "system"

def test_get_username_empty_context(sample_event_empty_context):
    """Test getting username when requestContext is empty."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    from utilities.auth import get_username

    username = get_username(sample_event_empty_context)
    assert username == "system"

def test_get_username_no_context(sample_event_no_context):
    """Test getting username when requestContext is missing."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    from utilities.auth import get_username

    username = get_username(sample_event_no_context)
    assert username == "system"

def test_get_username_nested_missing_authorizer():
    """Test getting username when authorizer is missing from requestContext."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    from utilities.auth import get_username

    event = {
        "requestContext": {
            "other_field": "value"
        }
    }
    username = get_username(event)
    assert username == "system"



def test_is_admin_with_admin_group(sample_event_with_username):
    """Test is_admin when user has admin group."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    with patch.dict(os.environ, {"ADMIN_GROUP": "admin"}):
        with patch("utilities.auth.get_groups", return_value=["group1", "admin", "group2"]):
            from utilities.auth import is_admin
            result = is_admin(sample_event_with_username)
            assert result is True

def test_is_admin_without_admin_group(sample_event_with_username):
    """Test is_admin when user does not have admin group."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    with patch.dict(os.environ, {"ADMIN_GROUP": "admin"}):
        with patch("utilities.auth.get_groups", return_value=["group1", "group2"]):
            from utilities.auth import is_admin
            result = is_admin(sample_event_with_username)
            assert result is False

def test_is_admin_empty_groups(sample_event_with_username):
    """Test is_admin when user has no groups."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    with patch.dict(os.environ, {"ADMIN_GROUP": "admin"}):
        with patch("utilities.auth.get_groups", return_value=[]):
            from utilities.auth import is_admin
            result = is_admin(sample_event_with_username)
            assert result is False

def test_is_admin_empty_admin_group_env(sample_event_with_username):
    """Test is_admin when ADMIN_GROUP environment variable is empty."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    with patch.dict(os.environ, {"ADMIN_GROUP": ""}):
        with patch("utilities.auth.get_groups", return_value=["group1", "group2"]):
            from utilities.auth import is_admin
            result = is_admin(sample_event_with_username)
            assert result is False

def test_is_admin_no_admin_group_env(sample_event_with_username):
    """Test is_admin when ADMIN_GROUP environment variable is not set."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    # Temporarily remove ADMIN_GROUP if it exists
    original_admin_group = os.environ.get("ADMIN_GROUP")
    if "ADMIN_GROUP" in os.environ:
        del os.environ["ADMIN_GROUP"]

    try:
        with patch("utilities.auth.get_groups", return_value=["group1", "group2"]):
            from utilities.auth import is_admin
            result = is_admin(sample_event_with_username)
            assert result is False
    finally:
        # Restore original value if it existed
        if original_admin_group is not None:
            os.environ["ADMIN_GROUP"] = original_admin_group

def test_is_admin_logging(sample_event_with_username):
    """Test is_admin logs the groups and admin group."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    with patch.dict(os.environ, {"ADMIN_GROUP": "admin"}):
        with patch("utilities.auth.get_groups", return_value=["group1", "admin"]):
            with patch("utilities.auth.logger") as mock_logger:
                from utilities.auth import is_admin
                is_admin(sample_event_with_username)
                mock_logger.info.assert_called_once_with("User groups: ['group1', 'admin'] and admin: admin")


def test_admin_only_decorator_with_admin_user(lambda_context):
    """Test admin_only decorator allows admin users to access function."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    with patch("utilities.auth.is_admin", return_value=True):
        from utilities.auth import admin_only
        
        @admin_only
        def test_function(event, context):
            return {"result": "success"}

        event = {"test": "data"}
        result = test_function(event, lambda_context)

    assert result == {"result": "success"}

def test_admin_only_decorator_with_non_admin_user(lambda_context):
    """Test admin_only decorator raises HTTPException for non-admin users."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    with patch("utilities.auth.is_admin", return_value=False):
        from utilities.auth import admin_only
        from utilities.exceptions import HTTPException

        @admin_only
        def test_function(event, context):
            return {"result": "success"}

        event = {"test": "data"}
        
        with pytest.raises(HTTPException) as exc_info:
            test_function(event, lambda_context)

        assert exc_info.value.http_status_code == 403
        assert exc_info.value.message == "User does not have permission to access this repository"

def test_admin_only_decorator_preserves_function_metadata():
    """Test admin_only decorator preserves original function metadata."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    from utilities.auth import admin_only

    @admin_only
    def test_function(event, context):
        """Test function docstring."""
        return {"result": "success"}

    assert test_function.__name__ == "test_function"
    assert test_function.__doc__ == "Test function docstring."

def test_admin_only_decorator_with_function_args_kwargs(lambda_context):
    """Test admin_only decorator works with functions that have additional args."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    with patch("utilities.auth.is_admin", return_value=True):
        from utilities.auth import admin_only

        @admin_only
        def test_function(event, context, *args, **kwargs):
            return {"result": "success", "args": args, "kwargs": kwargs}

        event = {"test": "data"}
        result = test_function(event, lambda_context, "arg1", "arg2", key1="value1")

    assert result["result"] == "success"
    assert result["args"] == ("arg1", "arg2")
    assert result["kwargs"] == {"key1": "value1"}


def test_admin_only_decorator_function_raises_exception(lambda_context):
    """Test admin_only decorator handles exceptions from wrapped function."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    with patch("utilities.auth.is_admin", return_value=True):
        from utilities.auth import admin_only

        @admin_only
        def test_function(event, context):
            raise ValueError("Test error")

        event = {"test": "data"}
        
        with pytest.raises(ValueError, match="Test error"):
            test_function(event, lambda_context)


def test_admin_only_decorator_calls_is_admin_with_event(lambda_context):
    """Test admin_only decorator calls is_admin with the event."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    with patch("utilities.auth.is_admin") as mock_is_admin:
        mock_is_admin.return_value = True
        from utilities.auth import admin_only

        @admin_only
        def test_function(event, context):
            return {"result": "success"}

        event = {"test": "data"}
        test_function(event, lambda_context)
        mock_is_admin.assert_called_once_with(event)


def test_full_auth_flow_admin_user():
    """Test full authentication flow for admin user."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    event = {
        "requestContext": {
            "authorizer": {
                "username": "admin-user",
                "groups": '["admin", "users"]'
            }
        }
    }

    with patch.dict(os.environ, {"ADMIN_GROUP": "admin"}):
        with patch("utilities.auth.get_groups", return_value=["admin", "users"]):
            from utilities.auth import get_username, is_admin
            username = get_username(event)
            admin_status = is_admin(event)

    assert username == "admin-user"
    assert admin_status is True


def test_full_auth_flow_regular_user():
    """Test full authentication flow for regular user."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    event = {
        "requestContext": {
            "authorizer": {
                "username": "regular-user",
                "groups": '["users"]'
            }
        }
    }

    with patch.dict(os.environ, {"ADMIN_GROUP": "admin"}):
        with patch("utilities.auth.get_groups", return_value=["users"]):
            from utilities.auth import get_username, is_admin
            username = get_username(event)
            admin_status = is_admin(event)

    assert username == "regular-user"
    assert admin_status is False


def test_system_user_auth_flow():
    """Test authentication flow for system user (no context)."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    event = {}

    with patch.dict(os.environ, {"ADMIN_GROUP": "admin"}):
        with patch("utilities.auth.get_groups", return_value=[]):
            from utilities.auth import get_username, is_admin
            username = get_username(event)
            admin_status = is_admin(event)

    assert username == "system"
    assert admin_status is False


def test_admin_only_decorator_with_extra_args(lambda_context):
    """Test admin_only decorator with additional args and kwargs."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    with patch("utilities.auth.is_admin", return_value=True):
        from utilities.auth import admin_only

        @admin_only
        def test_function(event, context, extra_arg, extra_kwarg=None):
            return {
                "result": "success",
                "extra_arg": extra_arg,
                "extra_kwarg": extra_kwarg
            }

        event = {"test": "data"}
        result = test_function(event, lambda_context, "test_arg", extra_kwarg="test_kwarg")

    assert result == {
        "result": "success",
        "extra_arg": "test_arg",
        "extra_kwarg": "test_kwarg"
    }


def test_admin_only_decorator_function_exception_propagation(lambda_context):
    """Test admin_only decorator allows underlying function exceptions to propagate."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    with patch("utilities.auth.is_admin", return_value=True):
        from utilities.auth import admin_only

        @admin_only
        def test_function(event, context):
            raise ValueError("Function error")

        event = {"test": "data"}
        
        with pytest.raises(ValueError) as exc_info:
            test_function(event, lambda_context)

        assert str(exc_info.value) == "Function error"


def test_admin_only_decorator_event_passing(lambda_context):
    """Test admin_only decorator calls is_admin with the correct event."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    with patch("utilities.auth.is_admin", return_value=True) as mock_is_admin:
        from utilities.auth import admin_only

        @admin_only
        def test_function(event, context):
            return {"result": "success"}

        event = {"test": "data"}
        test_function(event, lambda_context)

    mock_is_admin.assert_called_once_with(event)


def test_complete_auth_flow_admin_user(lambda_context):
    """Test complete auth flow for an admin user."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    event = {
        "requestContext": {
            "authorizer": {
                "username": "admin_user",
                "groups": '["user", "lisa-admin"]'
            }
        }
    }

    from utilities.auth import admin_only, get_username, is_admin
    
    # Test get_username
    username = get_username(event)
    assert username == "admin_user"

    # Test is_admin (need to mock get_groups)
    with patch.dict(os.environ, {"ADMIN_GROUP": "lisa-admin"}):
        with patch("utilities.auth.get_groups", return_value=["user", "lisa-admin"]):
            admin_status = is_admin(event)
            assert admin_status is True

            # Test admin_only decorator
            @admin_only
            def admin_function(event, context):
                return {"user": get_username(event), "admin": True}

            result = admin_function(event, lambda_context)
            assert result == {"user": "admin_user", "admin": True}


def test_complete_auth_flow_regular_user(lambda_context):
    """Test complete auth flow for a regular user."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    event = {
        "requestContext": {
            "authorizer": {
                "username": "regular_user",
                "groups": '["user"]'
            }
        }
    }

    from utilities.auth import admin_only, get_username, is_admin
    from utilities.exceptions import HTTPException
    
    # Test get_username
    username = get_username(event)
    assert username == "regular_user"

    # Test is_admin (need to mock get_groups)
    with patch.dict(os.environ, {"ADMIN_GROUP": "lisa-admin"}):
        with patch("utilities.auth.get_groups", return_value=["user"]):
            admin_status = is_admin(event)
            assert admin_status is False

            # Test admin_only decorator
            @admin_only
            def admin_function(event, context):
                return {"user": get_username(event), "admin": True}

            with pytest.raises(HTTPException) as exc_info:
                admin_function(event, lambda_context)

            assert exc_info.value.http_status_code == 403


def test_complete_system_user_auth_flow(lambda_context):
    """Test auth flow for system user (no context)."""
    if 'utilities.auth' in sys.modules:
        del sys.modules['utilities.auth']
    
    event = {}

    from utilities.auth import get_username, is_admin
    
    # Test get_username
    username = get_username(event)
    assert username == "system"

    # Test is_admin with system user
    with patch("utilities.auth.get_groups", return_value=[]):
        admin_status = is_admin(event)
        assert admin_status is False
