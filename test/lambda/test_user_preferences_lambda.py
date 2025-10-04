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

"""Test module for user preferences lambda functions - refactored version using fixture-based mocking."""

import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.config import Config
from moto import mock_aws


@pytest.fixture
def mock_user_preferences_common():
    """Common mocks for user preferences lambda functions."""

    def mock_api_wrapper(func):
        """Mock API wrapper that handles both success and error cases for testing."""

        def wrapper(event, context):
            try:
                result = func(event, context)
                if isinstance(result, dict) and "statusCode" in result:
                    return result
                return {
                    "statusCode": 200,
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                    "body": json.dumps(result, default=str),
                }
            except ValueError as e:
                error_msg = str(e)
                # Determine status code based on error message
                status_code = 400
                if "not found" in error_msg.lower():
                    status_code = 404
                elif "Not authorized" in error_msg:
                    status_code = 403

                return {
                    "statusCode": status_code,
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": error_msg}),
                }
            except Exception as e:
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": str(e)}),
                }

        return wrapper

    # Set up environment variables
    env_vars = {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SECURITY_TOKEN": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_REGION": "us-east-1",
        "USER_PREFERENCES_TABLE_NAME": "user-preferences-table",
    }

    retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")

    # Create mock UserPreferencesModel
    mock_user_preferences_model = MagicMock()
    mock_model_instance = MagicMock()
    mock_model_instance.model_dump.return_value = {
        "user": "test-user",
        "preferences": {"theme": "dark", "notifications": True},
    }
    mock_user_preferences_model.return_value = mock_model_instance

    with patch.dict(os.environ, env_vars), patch("utilities.auth.get_username") as mock_get_username, patch(
        "utilities.common_functions.retry_config", retry_config
    ), patch("utilities.common_functions.api_wrapper", mock_api_wrapper), patch(
        "utilities.common_functions.get_item"
    ) as mock_get_item, patch(
        "user_preferences.models.UserPreferencesModel", mock_user_preferences_model
    ), patch.dict(
        "sys.modules", {"create_env_variables": MagicMock()}
    ):

        # Set up default mock return values
        mock_get_username.return_value = "test-user"
        mock_get_item.return_value = None

        yield {
            "get_username": mock_get_username,
            "get_item": mock_get_item,
            "user_preferences_model": mock_user_preferences_model,
            "model_instance": mock_model_instance,
            "api_wrapper": mock_api_wrapper,
            "retry_config": retry_config,
        }


@pytest.fixture
def user_preferences_functions(mock_user_preferences_common):
    """Import user preferences lambda functions with mocked dependencies."""
    from user_preferences.lambda_functions import get, update

    return {
        "get": get,
        "update": update,
    }


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
def sample_user_preferences():
    """Sample user preferences for testing."""
    return {
        "user": "test-user",
        "preferences": {"theme": "dark", "notifications": True},
        "created": "2024-01-01T00:00:00Z",
        "modified": "2024-01-01T00:00:00Z",
    }


@pytest.fixture
def dynamodb_table():
    """Create a mock DynamoDB table for user preferences."""
    with mock_aws():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="user-preferences-table",
            KeySchema=[{"AttributeName": "user", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "user", "AttributeType": "S"}],
            ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
        )
        yield table


class TestGetUserPreferences:
    """Test class for getting user preferences."""

    def test_get_user_preferences_success(
        self,
        user_preferences_functions,
        mock_user_preferences_common,
        dynamodb_table,
        sample_user_preferences,
        lambda_context,
    ):
        """Test successfully getting user preferences."""
        # Add sample preferences to table
        dynamodb_table.put_item(Item=sample_user_preferences)

        # Mock get_item to return the sample preferences
        mock_user_preferences_common["get_item"].return_value = sample_user_preferences

        event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

        response = user_preferences_functions["get"](event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["user"] == "test-user"
        assert body["preferences"]["theme"] == "dark"
        assert body["preferences"]["notifications"] is True

    def test_get_user_preferences_not_found(
        self, user_preferences_functions, mock_user_preferences_common, dynamodb_table, lambda_context
    ):
        """Test getting user preferences when none exist."""
        # Mock get_item to return None
        mock_user_preferences_common["get_item"].return_value = None

        event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

        response = user_preferences_functions["get"](event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body is None

    def test_get_user_preferences_unauthorized(
        self, user_preferences_functions, mock_user_preferences_common, dynamodb_table, lambda_context
    ):
        """Test getting user preferences for unauthorized user."""
        # Mock get_item to return preferences for a different user
        other_user_preferences = {"user": "other-user", "preferences": {"theme": "light"}}
        mock_user_preferences_common["get_item"].return_value = other_user_preferences

        event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

        response = user_preferences_functions["get"](event, lambda_context)

        assert response["statusCode"] == 403
        body = json.loads(response["body"])
        assert "Not authorized to get test-user's preferences" in body["error"]

    def test_get_user_preferences_missing_claims(
        self, user_preferences_functions, mock_user_preferences_common, lambda_context
    ):
        """Test getting user preferences with missing claims."""
        # Mock get_username to raise ValueError
        mock_user_preferences_common["get_username"].side_effect = ValueError("Missing username")

        event = {"requestContext": {"authorizer": {}}}

        response = user_preferences_functions["get"](event, lambda_context)

        assert response["statusCode"] == 400  # ValueError is treated as 400 in mock_api_wrapper
        body = json.loads(response["body"])
        assert "error" in body

        # Reset the mock
        mock_user_preferences_common["get_username"].side_effect = None
        mock_user_preferences_common["get_username"].return_value = "test-user"

    def test_get_user_preferences_query_error(self, user_preferences_functions, dynamodb_table, lambda_context):
        """Test getting user preferences with database query error."""
        # Mock the table.query method to raise an exception
        with patch("user_preferences.lambda_functions.table") as mock_table:
            mock_table.query.side_effect = Exception("Database error")

            event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

            response = user_preferences_functions["get"](event, lambda_context)

            assert response["statusCode"] == 500  # General exceptions are 500
            body = json.loads(response["body"])
            assert "error" in body

    def test_get_user_preferences_complex_data(
        self, user_preferences_functions, mock_user_preferences_common, dynamodb_table, lambda_context
    ):
        """Test getting user preferences with complex nested data."""
        complex_preferences = {
            "user": "test-user",
            "preferences": {
                "ui": {"theme": "dark", "sidebar": {"collapsed": True, "width": 300}},
                "notifications": {"email": True, "push": False, "frequency": "daily"},
                "features": ["feature1", "feature2"],
            },
        }

        mock_user_preferences_common["get_item"].return_value = complex_preferences

        event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

        response = user_preferences_functions["get"](event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["user"] == "test-user"
        assert body["preferences"]["ui"]["theme"] == "dark"
        assert body["preferences"]["notifications"]["email"] is True
        assert "feature1" in body["preferences"]["features"]

    def test_get_user_preferences_case_sensitivity(
        self, user_preferences_functions, mock_user_preferences_common, dynamodb_table, lambda_context
    ):
        """Test that user preferences are case sensitive for user IDs."""
        # Mock get_item to return preferences for exact user match
        user_preferences = {"user": "Test-User", "preferences": {"theme": "dark"}}  # Different case
        mock_user_preferences_common["get_item"].return_value = user_preferences

        # User ID is "test-user" but preferences are for "Test-User"
        event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

        response = user_preferences_functions["get"](event, lambda_context)

        assert response["statusCode"] == 403
        body = json.loads(response["body"])
        assert "Not authorized" in body["error"]

    def test_get_user_preferences_empty_table(
        self, user_preferences_functions, mock_user_preferences_common, dynamodb_table, lambda_context
    ):
        """Test getting user preferences from an empty table."""
        # Mock get_item to return None (empty table)
        mock_user_preferences_common["get_item"].return_value = None

        event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}}

        response = user_preferences_functions["get"](event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body is None


class TestUpdateUserPreferences:
    """Test class for updating user preferences."""

    def test_update_user_preferences_new_user(
        self, user_preferences_functions, mock_user_preferences_common, dynamodb_table, lambda_context
    ):
        """Test updating user preferences for a new user (create new preferences)."""
        # Mock get_item to return None (no existing preferences)
        mock_user_preferences_common["get_item"].return_value = None

        preferences_data = {"theme": "dark", "notifications": True}
        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "body": json.dumps(preferences_data),
        }

        response = user_preferences_functions["update"](event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["user"] == "test-user"
        assert body["preferences"]["theme"] == "dark"

    def test_update_user_preferences_existing_user(
        self,
        user_preferences_functions,
        mock_user_preferences_common,
        dynamodb_table,
        sample_user_preferences,
        lambda_context,
    ):
        """Test updating user preferences for an existing user."""
        # Mock get_item to return existing preferences
        mock_user_preferences_common["get_item"].return_value = sample_user_preferences

        updated_preferences = {"theme": "light", "notifications": False}
        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "body": json.dumps(updated_preferences),
        }

        response = user_preferences_functions["update"](event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["user"] == "test-user"

    def test_update_user_preferences_unauthorized(
        self, user_preferences_functions, mock_user_preferences_common, dynamodb_table, lambda_context
    ):
        """Test updating user preferences when unauthorized."""
        # Mock get_item to return preferences for a different user
        other_user_preferences = {"user": "other-user", "preferences": {"theme": "light"}}
        mock_user_preferences_common["get_item"].return_value = other_user_preferences

        preferences_data = {"theme": "dark"}
        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "body": json.dumps(preferences_data),
        }

        response = user_preferences_functions["update"](event, lambda_context)

        assert response["statusCode"] == 403
        body = json.loads(response["body"])
        assert "Not authorized to update test-user's preferences" in body["error"]

    def test_update_user_preferences_with_decimal_values(
        self, user_preferences_functions, mock_user_preferences_common, dynamodb_table, lambda_context
    ):
        """Test updating user preferences with decimal values in JSON."""
        # Mock get_item to return None (new user)
        mock_user_preferences_common["get_item"].return_value = None

        preferences_data = {"fontSize": 14.5, "maxItems": 100}
        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "body": json.dumps(preferences_data),
        }

        response = user_preferences_functions["update"](event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["user"] == "test-user"

    def test_update_user_preferences_invalid_json(self, user_preferences_functions, dynamodb_table, lambda_context):
        """Test updating user preferences with invalid JSON."""
        event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}, "body": "invalid-json"}

        response = user_preferences_functions["update"](event, lambda_context)

        assert response["statusCode"] == 400  # JSON parsing errors are handled as ValueError, so 400
        body = json.loads(response["body"])
        assert "error" in body

    def test_update_user_preferences_missing_claims(
        self, user_preferences_functions, mock_user_preferences_common, lambda_context
    ):
        """Test updating user preferences with missing claims."""
        # Mock get_username to raise ValueError
        mock_user_preferences_common["get_username"].side_effect = ValueError("Missing username")

        event = {"requestContext": {"authorizer": {}}, "body": json.dumps({"theme": "dark"})}

        response = user_preferences_functions["update"](event, lambda_context)

        assert response["statusCode"] == 400  # ValueError is treated as 400 in mock_api_wrapper
        body = json.loads(response["body"])
        assert "error" in body

        # Reset the mock
        mock_user_preferences_common["get_username"].side_effect = None
        mock_user_preferences_common["get_username"].return_value = "test-user"

    def test_update_user_preferences_model_validation_error(
        self, user_preferences_functions, mock_user_preferences_common, dynamodb_table, lambda_context
    ):
        """Test updating user preferences with model validation error."""
        # Mock get_item to return None (new user)
        mock_user_preferences_common["get_item"].return_value = None

        # Mock UserPreferencesModel to raise validation error
        mock_user_preferences_common["user_preferences_model"].side_effect = ValueError("Validation error")

        preferences_data = {"invalid": "data"}
        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "body": json.dumps(preferences_data),
        }

        response = user_preferences_functions["update"](event, lambda_context)

        assert response["statusCode"] == 400  # ValueError is treated as 400 in mock_api_wrapper
        body = json.loads(response["body"])
        assert "error" in body

        # Reset the mock
        mock_user_preferences_common["user_preferences_model"].side_effect = None
        mock_user_preferences_common["user_preferences_model"].return_value = mock_user_preferences_common[
            "model_instance"
        ]

    def test_update_user_preferences_put_error(self, user_preferences_functions, dynamodb_table, lambda_context):
        """Test updating user preferences with database put error."""
        # Mock the table.put_item method to raise an exception
        with patch("user_preferences.lambda_functions.table") as mock_table:
            mock_table.put_item.side_effect = Exception("Database error")

            preferences_data = {"theme": "dark"}
            event = {
                "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
                "body": json.dumps(preferences_data),
            }

            response = user_preferences_functions["update"](event, lambda_context)

            assert response["statusCode"] == 500  # General exceptions are 500
            body = json.loads(response["body"])
            assert "error" in body

    def test_update_user_preferences_empty_body(
        self, user_preferences_functions, mock_user_preferences_common, dynamodb_table, lambda_context
    ):
        """Test updating user preferences with empty body."""
        # Mock get_item to return None (new user)
        mock_user_preferences_common["get_item"].return_value = None

        event = {"requestContext": {"authorizer": {"claims": {"username": "test-user"}}}, "body": "{}"}

        response = user_preferences_functions["update"](event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["user"] == "test-user"

    def test_update_user_preferences_with_special_characters(
        self, user_preferences_functions, mock_user_preferences_common, dynamodb_table, lambda_context
    ):
        """Test updating user preferences with special characters and unicode."""
        # Mock get_item to return None (new user)
        mock_user_preferences_common["get_item"].return_value = None

        preferences_data = {
            "displayName": "Test User 🚀",
            "locale": "en-US",
            "customText": "Special chars: àáâãäåæçèéêë",
            "emoji": "👍",
        }

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "body": json.dumps(preferences_data, ensure_ascii=False),
        }

        response = user_preferences_functions["update"](event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["user"] == "test-user"

    def test_update_user_preferences_large_payload(
        self, user_preferences_functions, mock_user_preferences_common, dynamodb_table, lambda_context
    ):
        """Test updating user preferences with a large JSON payload."""
        # Mock get_item to return None (new user)
        mock_user_preferences_common["get_item"].return_value = None

        # Create a large preferences object
        large_preferences = {
            "settings": {f"setting_{i}": f"value_{i}" for i in range(100)},
            "customizations": {f"custom_{i}": {"option": f"value_{i}"} for i in range(50)},
            "history": [f"item_{i}" for i in range(200)],
        }

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "body": json.dumps(large_preferences),
        }

        response = user_preferences_functions["update"](event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["user"] == "test-user"

    def test_update_user_preferences_none_values(
        self, user_preferences_functions, mock_user_preferences_common, dynamodb_table, lambda_context
    ):
        """Test updating user preferences with None values."""
        # Mock get_item to return None (new user)
        mock_user_preferences_common["get_item"].return_value = None

        preferences_data = {"theme": None, "notifications": None, "validSetting": "value"}

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "body": json.dumps(preferences_data),
        }

        response = user_preferences_functions["update"](event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["user"] == "test-user"

    def test_update_user_preferences_boolean_values(
        self, user_preferences_functions, mock_user_preferences_common, dynamodb_table, lambda_context
    ):
        """Test updating user preferences with various boolean values."""
        # Mock get_item to return None (new user)
        mock_user_preferences_common["get_item"].return_value = None

        preferences_data = {
            "setting1": True,
            "setting2": False,
            "setting3": 0,
            "setting4": 1,
            "setting5": "true",
            "setting6": "false",
        }

        event = {
            "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
            "body": json.dumps(preferences_data),
        }

        response = user_preferences_functions["update"](event, lambda_context)

        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["user"] == "test-user"
