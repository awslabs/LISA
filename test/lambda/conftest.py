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

"""Common test fixtures and utilities for lambda function tests."""

import functools
import json
import logging
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from botocore.config import Config

# Create a real retry config
retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")


def mock_api_wrapper(func):
    """Mock API wrapper that handles both success and error cases for testing."""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            if isinstance(result, dict) and "statusCode" in result:
                return result
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps(result, default=str),
            }
        except ValueError as e:
            error_msg = str(e)
            status_code = 400
            if "not found" in error_msg.lower():
                status_code = 404
            elif "Not authorized" in error_msg or "not authorized" in error_msg:
                status_code = 403
            return {
                "statusCode": status_code,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": error_msg}, default=str),
            }
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {str(e)}")
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": str(e)}),
            }

    return wrapper


class MockAuth:
    """Mock authentication helper for testing."""

    def __init__(self):
        self.username = "test-user"
        self.groups = ["test-group"]
        self.is_admin_value = False

        # Create mock functions with side_effect that references self attributes
        self.get_username = MagicMock(side_effect=lambda event: self.username)
        self.get_groups = MagicMock(side_effect=lambda event: self.groups)
        self.is_admin = MagicMock(side_effect=lambda event: self.is_admin_value)
        self.get_user_context = MagicMock(side_effect=lambda event: (self.username, self.is_admin_value, self.groups))

    def set_user(self, username="test-user", groups=None, is_admin=False):
        """Set the current user context."""
        self.username = username
        self.groups = groups if groups is not None else ["test-group"]
        self.is_admin_value = is_admin
        # side_effect lambdas will automatically use updated self attributes

    def reset(self):
        """Reset to default test user."""
        self.set_user()


@pytest.fixture(scope="function")
def mock_auth():
    """Provide a MockAuth instance for tests."""
    auth = MockAuth()
    # Ensure default user is set
    auth.set_user("test-user", ["test-group"], False)
    return auth


@pytest.fixture(autouse=True)
def setup_auth_patches(request, mock_auth, aws_credentials):
    """Automatically patch auth functions for all tests except test_auth.py."""
    # Skip patching for test_auth.py since it tests the auth module itself
    if "test_auth" in request.node.nodeid:
        yield mock_auth
        return

    # Reset the auth provider singleton to ensure clean state between tests
    try:
        import utilities.auth_provider as auth_provider_module

        auth_provider_module._auth_provider = None
    except ImportError:
        pass

    patches = [
        patch("utilities.auth.get_username", mock_auth.get_username),
        patch("utilities.auth.get_groups", mock_auth.get_groups),
        patch("utilities.auth.is_admin", mock_auth.is_admin),
        patch("utilities.auth.get_user_context", mock_auth.get_user_context),
        # Also patch where these functions are imported
        patch("models.lambda_functions.is_admin", mock_auth.is_admin),
        patch("models.lambda_functions.get_groups", mock_auth.get_groups),
        patch("utilities.fastapi_middleware.auth_decorators.is_admin", mock_auth.is_admin),
    ]

    for p in patches:
        p.start()

    yield mock_auth

    for p in patches:
        p.stop()

    mock_auth.reset()

    # Reset the auth provider singleton after test
    try:
        import utilities.auth_provider as auth_provider_module

        auth_provider_module._auth_provider = None
    except ImportError:
        pass


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


@pytest.fixture(scope="function")
def aws_credentials():
    """Mocked AWS Credentials for moto."""
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
    os.environ["AWS_REGION"] = "us-east-1"


@pytest.fixture
def setup_env():
    """Setup environment for auth tests."""
    # This is a no-op fixture for test_auth.py compatibility
    yield


# Export commonly used items
__all__ = [
    "mock_auth",
    "setup_auth_patches",
    "lambda_context",
    "aws_credentials",
    "mock_api_wrapper",
    "retry_config",
    "MockAuth",
]
