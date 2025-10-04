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

import functools
import json
import logging
import os
import sys
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.config import Config
from botocore.exceptions import ClientError
from moto import mock_aws

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["CONFIG_TABLE_NAME"] = "config-table"


@pytest.fixture(scope="function")
def dynamodb():
    """Create a mock DynamoDB service."""
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture(scope="function")
def config_table(dynamodb):
    """Create a mock DynamoDB table for configuration."""
    table = dynamodb.create_table(
        TableName="config-table",
        KeySchema=[
            {"AttributeName": "configScope", "KeyType": "HASH"},
            {"AttributeName": "configKey", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "configScope", "AttributeType": "S"},
            {"AttributeName": "configKey", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return table


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
def sample_config_items():
    """Create sample configuration items."""
    return [
        {
            "configScope": "system",
            "configKey": "default_model",
            "value": "gpt-3.5-turbo",
            "created_at": "1648677600",
        },
        {
            "configScope": "system",
            "configKey": "max_tokens",
            "value": 2048,
            "created_at": "1648677600",
        },
        {
            "configScope": "user",
            "configKey": "theme",
            "value": "dark",
            "created_at": "1648677600",
        },
    ]


@pytest.fixture
def mock_configuration_common():
    """Mock common functions for configuration tests."""
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

                return {
                    "statusCode": status_code,
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": error_msg}),
                }
            except Exception as e:
                logging.error(f"Error in {func.__name__}: {str(e)}")
                return {
                    "statusCode": 500,
                    "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                    "body": json.dumps({"error": str(e)}),
                }

        return wrapper

    with patch("utilities.common_functions.retry_config", retry_config), patch(
        "utilities.common_functions.api_wrapper", mock_api_wrapper
    ):
        yield


@pytest.fixture
def mock_create_env_variables():
    """Mock create_env_variables module."""
    with patch.dict("sys.modules", {"create_env_variables": MagicMock()}):
        yield


@pytest.fixture
def configuration_functions(mock_configuration_common, mock_create_env_variables):
    """Import configuration functions with mocked dependencies."""
    from configuration.lambda_functions import get_configuration, update_configuration

    return {
        "get_configuration": get_configuration,
        "update_configuration": update_configuration,
    }


def test_get_configuration_system(configuration_functions, config_table, sample_config_items, lambda_context):
    """Test getting system configuration."""
    get_configuration = configuration_functions["get_configuration"]

    # Add items to the table
    for item in sample_config_items:
        config_table.put_item(Item=item)

    # Create test event
    event = {"queryStringParameters": {"configScope": "system"}}

    # Call the function
    response = get_configuration(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body) == 2
    assert any(item["configKey"] == "default_model" for item in body)
    assert any(item["configKey"] == "max_tokens" for item in body)


def test_get_configuration_user(configuration_functions, config_table, sample_config_items, lambda_context):
    """Test getting user configuration."""
    get_configuration = configuration_functions["get_configuration"]

    # Add items to the table
    for item in sample_config_items:
        config_table.put_item(Item=item)

    # Create test event
    event = {"queryStringParameters": {"configScope": "user"}}

    # Call the function
    response = get_configuration(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert len(body) == 1
    assert body[0]["configKey"] == "theme"
    assert body[0]["value"] == "dark"


def test_get_configuration_empty(configuration_functions, config_table, lambda_context):
    """Test getting configuration with no results."""
    get_configuration = configuration_functions["get_configuration"]

    # Create test event
    event = {"queryStringParameters": {"configScope": "nonexistent"}}

    # Call the function
    response = get_configuration(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body == []


def test_get_configuration_missing_param(configuration_functions, lambda_context):
    """Test getting configuration with missing parameter."""
    get_configuration = configuration_functions["get_configuration"]

    # Create test event with missing configScope
    event = {"queryStringParameters": {}}

    # Call the function
    response = get_configuration(event, lambda_context)

    # Should return error due to KeyError
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "error" in body


def test_get_configuration_resource_not_found(configuration_functions, config_table, lambda_context):
    """Test handling ResourceNotFoundException."""
    get_configuration = configuration_functions["get_configuration"]

    # Create test event
    event = {"queryStringParameters": {"configScope": "system"}}

    # Mock the DynamoDB client to raise ResourceNotFoundException
    with patch("boto3.resource") as mock_resource:
        mock_table = MagicMock()
        mock_table.query.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}}, "Query"
        )
        mock_resource.return_value.Table.return_value = mock_table

        # Call the function
        response = get_configuration(event, lambda_context)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body == []


def test_get_configuration_client_error(configuration_functions, config_table, lambda_context):
    """Test handling other ClientError."""
    get_configuration = configuration_functions["get_configuration"]

    # Create test event
    event = {"queryStringParameters": {"configScope": "system"}}

    # Mock the DynamoDB client to raise ClientError
    with patch("boto3.resource") as mock_resource:
        mock_table = MagicMock()
        mock_table.query.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Internal error"}}, "Query"
        )
        mock_resource.return_value.Table.return_value = mock_table

        # Call the function
        response = get_configuration(event, lambda_context)

        # Verify response
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body == []


def test_get_configuration_none_query_string_parameters(configuration_functions, lambda_context):
    """Test getting configuration with None queryStringParameters."""
    get_configuration = configuration_functions["get_configuration"]

    # Create test event with None queryStringParameters
    event = {
        # queryStringParameters is None
    }

    # Call the function
    response = get_configuration(event, lambda_context)

    # Should return error due to KeyError
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "error" in body


def test_get_configuration_resource_not_found_specific(configuration_functions, config_table, lambda_context):
    """Test specifically the ResourceNotFoundException branch."""
    get_configuration = configuration_functions["get_configuration"]

    # Create test event
    event = {"queryStringParameters": {"configScope": "system"}}

    # We need to patch the specific logger instance that's used in the configuration.lambda_functions module
    with patch("configuration.lambda_functions.logger") as mock_logger:
        # Mock the DynamoDB to raise ResourceNotFoundException specifically
        with patch("configuration.lambda_functions.table") as mock_table:
            # Create a ClientError with the specific code "ResourceNotFoundException"
            mock_table.query.side_effect = ClientError(
                {"Error": {"Code": "ResourceNotFoundException", "Message": "Resource not found"}}, "Query"
            )

            # Call the function
            response = get_configuration(event, lambda_context)

            # Verify the response
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body == {}  # The response is an empty dict here because we mock at a lower level

            # Verify that logger.warning was called with the expected message
            mock_logger.warning.assert_called_once_with("No record found with session id: system")


def test_update_configuration(configuration_functions, config_table, lambda_context):
    """Test updating configuration."""
    update_configuration = configuration_functions["update_configuration"]

    # Create test event
    test_config = {"configScope": "system", "configKey": "new_setting", "value": "new_value"}

    event = {"body": json.dumps(test_config)}

    # Call the function
    response = update_configuration(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200

    # Verify the item was added to the table
    response = config_table.get_item(Key={"configScope": "system", "configKey": "new_setting"})

    item = response.get("Item")
    assert item is not None
    assert item["configScope"] == "system"
    assert item["configKey"] == "new_setting"
    assert item["value"] == "new_value"
    assert "created_at" in item


def test_update_configuration_with_decimal(configuration_functions, config_table, lambda_context):
    """Test updating configuration with a decimal value."""
    update_configuration = configuration_functions["update_configuration"]

    # Create test event with a decimal value
    test_config = {"configScope": "system", "configKey": "token_limit", "value": 1000.5}

    event = {"body": json.dumps(test_config)}

    # Call the function
    response = update_configuration(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200

    # Verify the item was added to the table with Decimal
    response = config_table.get_item(Key={"configScope": "system", "configKey": "token_limit"})

    item = response.get("Item")
    assert item is not None
    assert item["value"] == Decimal("1000.5")


def test_update_configuration_invalid_json(configuration_functions, lambda_context):
    """Test updating configuration with invalid JSON."""
    update_configuration = configuration_functions["update_configuration"]

    # Create test event with invalid JSON
    event = {"body": "invalid-json"}

    # Call the function
    response = update_configuration(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert "error" in body
    assert "Expecting value" in str(body["error"])


def test_update_configuration_client_error(configuration_functions, lambda_context):
    """Test handling ClientError during update."""
    update_configuration = configuration_functions["update_configuration"]

    # Create test event
    test_config = {"configScope": "system", "configKey": "new_setting", "value": "new_value"}

    event = {"body": json.dumps(test_config)}

    # We need to patch at a more specific level to properly handle the ClientError case
    with patch("configuration.lambda_functions.table") as mock_table:
        mock_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "Internal error"}}, "PutItem"
        )

        # Call the function
        response = update_configuration(event, lambda_context)

        # Verify response
        assert response["statusCode"] == 200  # The function still returns 200 even with errors
        # The ClientError is caught and logged, but the function returns None
        # Our mock_api_wrapper wraps this as a 200 response with an empty body
        assert response["body"] == "null"


def test_update_configuration_complex_data(configuration_functions, config_table, lambda_context):
    """Test updating configuration with complex nested data."""
    update_configuration = configuration_functions["update_configuration"]

    # Create test event with complex nested data
    test_config = {
        "configScope": "system",
        "configKey": "complex_setting",
        "value": {"nested": {"array": [1, 2, 3], "object": {"key": "value"}}, "boolean": True, "null_value": None},
    }

    event = {"body": json.dumps(test_config)}

    # Call the function
    response = update_configuration(event, lambda_context)

    # Verify response
    assert response["statusCode"] == 200

    # Verify the item was added to the table
    response = config_table.get_item(Key={"configScope": "system", "configKey": "complex_setting"})

    item = response.get("Item")
    assert item is not None
    assert item["configScope"] == "system"
    assert item["configKey"] == "complex_setting"
    assert "value" in item
    assert "nested" in item["value"]
    assert "boolean" in item["value"]
    assert item["value"]["boolean"] is True
    assert "created_at" in item


def test_get_configuration_other_client_error_specific(configuration_functions, config_table, lambda_context):
    """Test specifically the other ClientError branch in get_configuration."""
    get_configuration = configuration_functions["get_configuration"]

    # Create test event
    event = {"queryStringParameters": {"configScope": "system"}}

    # We need to patch the specific logger instance that's used in the configuration.lambda_functions module
    with patch("configuration.lambda_functions.logger") as mock_logger:
        # Mock the DynamoDB to raise some other ClientError
        with patch("configuration.lambda_functions.table") as mock_table:
            # Create a ClientError with a code other than "ResourceNotFoundException"
            mock_table.query.side_effect = ClientError(
                {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}}, "Query"
            )

            # Call the function
            response = get_configuration(event, lambda_context)

            # Verify the response
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body == {}

            # Verify that logger.exception was called with the expected message
            mock_logger.exception.assert_called_once_with("Error fetching session")
