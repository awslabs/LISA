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
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import ANY, call, MagicMock, patch

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
os.environ["USER_METRICS_TABLE_NAME"] = "user-metrics-table"


retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")


def mock_api_wrapper(func):
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
        except Exception as e:
            logging.error(f"Error in {func.__name__}: {str(e)}")
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": str(e)}),
            }

    return wrapper


@pytest.fixture(scope="function")
def dynamodb():
    """Create a mock DynamoDB service."""
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture(scope="function")
def cloudwatch():
    """Create a mock CloudWatch service."""
    with mock_aws():
        yield boto3.client("cloudwatch", region_name="us-east-1")


@pytest.fixture(scope="function")
def dynamodb_table(dynamodb):
    """Create a mock DynamoDB table for user metrics."""
    table = dynamodb.create_table(
        TableName="user-metrics-table",
        KeySchema=[{"AttributeName": "userId", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "userId", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return table


@pytest.fixture
def sample_user_metrics():
    """Sample user metrics data."""
    return {
        "userId": "test-user-1",
        "totalPrompts": 10,
        "ragUsageCount": 5,
        "firstSeen": datetime.now().isoformat(),
        "lastSeen": datetime.now().isoformat(),
        "userGroups": {"group1", "group2"},
    }


@pytest.fixture
def multiple_user_metrics(dynamodb_table):
    """Create multiple user metrics entries."""
    items = [
        {
            "userId": "test-user-1",
            "totalPrompts": 10,
            "ragUsageCount": 5,
            "firstSeen": datetime.now().isoformat(),
            "lastSeen": datetime.now().isoformat(),
            "userGroups": {"group1", "group2"},
        },
        {
            "userId": "test-user-2",
            "totalPrompts": 20,
            "ragUsageCount": 10,
            "firstSeen": datetime.now().isoformat(),
            "lastSeen": datetime.now().isoformat(),
            "userGroups": {"group1", "group3"},
        },
        {
            "userId": "test-user-3",
            "totalPrompts": 5,
            "ragUsageCount": 2,
            "firstSeen": datetime.now().isoformat(),
            "lastSeen": datetime.now().isoformat(),
            "userGroups": {"group2", "group3"},
        },
    ]

    for item in items:
        dynamodb_table.put_item(Item=item)

    return items


# Create mock modules
mock_common = MagicMock()
mock_common.retry_config = retry_config
mock_common.api_wrapper = mock_api_wrapper

# Create mock create_env_variables
mock_create_env = MagicMock()

# Patch sys.modules with mocks BEFORE importing the modules that use them
patch.dict(
    "sys.modules",
    {
        "create_env_variables": mock_create_env,
        "utilities.common_functions": mock_common,
    },
).start()

# Patch the specific functions
patch("utilities.common_functions.retry_config", retry_config).start()
patch("utilities.common_functions.api_wrapper", mock_api_wrapper).start()

# Module to test can be imported now that dependencies are mocked
from metrics.lambda_functions import (
    check_rag_usage,
    count_unique_users_and_publish_metric,
    count_users_by_group_and_publish_metric,
    daily_metrics_handler,
    get_global_metrics,
    get_user_metrics,
    process_metrics_sqs_event,
    update_user_metrics,
)


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context."""
    return SimpleNamespace(
        function_name="test_metrics_function",
        function_version="$LATEST",
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test_metrics_function",
        memory_limit_in_mb=128,
        aws_request_id="test-request-id",
        log_group_name="/aws/lambda/test_metrics_function",
        log_stream_name="2024/03/27/[$LATEST]test123",
    )


class TestGetUserMetrics:
    def test_get_user_metrics_success(self, dynamodb_table, sample_user_metrics, lambda_context):
        """Test getting user metrics successfully.

        Expected: Should return user metrics with 200 status code when userId exists.
        """
        # Insert sample data into table
        dynamodb_table.put_item(Item=sample_user_metrics)

        # get user metrics
        event = {"pathParameters": {"userId": "test-user-1"}}
        response = get_user_metrics(event, lambda_context)

        # Assert success
        assert response["statusCode"] == 200
        body = response["body"]
        assert body["test-user-1"]["totalPrompts"] == 10
        assert body["test-user-1"]["ragUsageCount"] == 5
        assert set(body["test-user-1"]["userGroups"]) == {"group1", "group2"}

    def test_get_user_metrics_missing_user_id(self, lambda_context):
        """Test getting user metrics with missing userId parameter.

        Expected: Should return 400 status code when userId is missing from pathParameters.
        """
        event = {"pathParameters": {}}
        response = get_user_metrics(event, lambda_context)

        assert response["statusCode"] == 400
        assert "Missing userId" in json.loads(response["body"])["error"]

    def test_get_user_metrics_no_path_parameters(self, lambda_context):
        """Test getting user metrics with no pathParameters.

        Expected: Should return 400 status code when pathParameters is missing entirely.
        """
        event = {}
        response = get_user_metrics(event, lambda_context)

        assert response["statusCode"] == 400
        assert "Missing userId" in json.loads(response["body"])["error"]

    def test_get_user_metrics_user_not_found(self, dynamodb_table, lambda_context):
        """Test getting metrics for a user that doesn't exist.

        Expected: Should return 200 status code with default empty metrics when user doesn't exist.
        """
        event = {"pathParameters": {"userId": "non-existent-user"}}
        response = get_user_metrics(event, lambda_context)

        assert response["statusCode"] == 200
        body = response["body"]
        assert body["non-existent-user"]["totalPrompts"] == 0
        assert body["non-existent-user"]["ragUsageCount"] == 0
        assert body["non-existent-user"]["userGroups"] == []

    def test_get_user_metrics_exception_handling(self, lambda_context):
        """Test exception handling in get_user_metrics.

        Expected: Should return 500 status code when an exception occurs.
        """
        with patch("metrics.lambda_functions.metrics_table.get_item") as mock_get_item:
            mock_get_item.side_effect = Exception("Test exception")

            event = {"pathParameters": {"userId": "test-user-1"}}
            response = get_user_metrics(event, lambda_context)

            assert response["statusCode"] == 500
            # The error message from the exception is passed through
            assert "Test exception" in json.loads(response["body"])["error"]


class TestGetGlobalMetrics:
    def test_get_global_metrics_success(self, dynamodb_table, multiple_user_metrics, lambda_context):
        """Test getting global metrics successfully.

        Expected: Should return aggregated metrics across all users with correct calculations.
        """
        event = {}
        response = get_global_metrics(event, lambda_context)

        assert response["statusCode"] == 200
        body = response["body"]

        # Verify calculated metrics
        assert body["totalUniqueUsers"] == 3
        assert body["totalPrompts"] == 35  # Sum of all user prompts (10 + 20 + 5)
        assert body["totalRagUsage"] == 17  # Sum of all RAG usage (5 + 10 + 2)
        # Calculate expected RAG percentage: (17/35) * 100 = 48.57...
        # Convert Decimal to float for comparison
        rag_percentage = float(body["ragUsagePercentage"])
        expected_percentage = 17 / 35 * 100
        assert abs(rag_percentage - expected_percentage) < 0.01

        # Verify user groups
        assert body["userGroups"]["group1"] == 2
        assert body["userGroups"]["group2"] == 2
        assert body["userGroups"]["group3"] == 2

    def test_get_global_metrics_empty_table(self, dynamodb_table, lambda_context):
        """Test getting global metrics from an empty table.

        Expected: Should return zero metrics when there are no users in the table.
        """
        event = {}
        response = get_global_metrics(event, lambda_context)

        assert response["statusCode"] == 200
        body = response["body"]

        assert body["totalUniqueUsers"] == 0
        assert body["totalPrompts"] == 0
        assert body["totalRagUsage"] == 0
        assert body["ragUsagePercentage"] == 0
        assert body["userGroups"] == {}

    def test_get_global_metrics_exception_handling(self, lambda_context):
        """Test exception handling in get_global_metrics.

        Expected: Should return 500 status code when an exception occurs during metric retrieval.
        """
        with patch("metrics.lambda_functions.metrics_table.scan") as mock_scan:
            mock_scan.side_effect = Exception("Test exception")

            event = {}
            response = get_global_metrics(event, lambda_context)

            assert response["statusCode"] == 500
            # The error message from the exception is passed through
            assert "Test exception" in json.loads(response["body"])["error"]


class TestCloudwatchMetrics:
    def test_count_unique_users_and_publish_metric(self, dynamodb_table, multiple_user_metrics):
        """Test counting unique users and publishing to CloudWatch.

        Expected: Should count users correctly and publish metrics to CloudWatch.
        """
        with patch("metrics.lambda_functions.cloudwatch.put_metric_data") as mock_put_metric:
            result = count_unique_users_and_publish_metric()

            assert result == 3  # 3 users in test data

            # Verify CloudWatch was called correctly
            mock_put_metric.assert_called_once()
            args = mock_put_metric.call_args[1]
            assert args["Namespace"] == "LISA/UserMetrics"
            assert len(args["MetricData"]) == 1
            assert args["MetricData"][0]["MetricName"] == "UniqueUsers"
            assert args["MetricData"][0]["Value"] == 3
            assert args["MetricData"][0]["Unit"] == "Count"

    def test_count_users_by_group_and_publish_metric(self, dynamodb_table, multiple_user_metrics):
        """Test counting users by group and publishing to CloudWatch.

        Expected: Should count users by group correctly and publish metrics to CloudWatch.
        """
        with patch("metrics.lambda_functions.cloudwatch.put_metric_data") as mock_put_metric:
            result = count_users_by_group_and_publish_metric()

            # Check that we got the expected group counts
            assert result["group1"] == 2
            assert result["group2"] == 2
            assert result["group3"] == 2

            # Verify CloudWatch was called correctly
            mock_put_metric.assert_called_once()
            args = mock_put_metric.call_args[1]
            assert args["Namespace"] == "LISA/UserMetrics"
            assert len(args["MetricData"]) == 3  # 3 groups

            # Check that all groups have metrics
            metrics = {m["Dimensions"][0]["Value"]: m["Value"] for m in args["MetricData"]}
            assert metrics["group1"] == 2
            assert metrics["group2"] == 2
            assert metrics["group3"] == 2

    def test_daily_metrics_handler(self, dynamodb_table, multiple_user_metrics, lambda_context):
        """Test the daily metrics handler function.

        Expected: Should call both metrics functions and return the combined results.
        """
        with patch("metrics.lambda_functions.count_unique_users_and_publish_metric") as mock_count_users, patch(
            "metrics.lambda_functions.count_users_by_group_and_publish_metric"
        ) as mock_count_by_group:

            mock_count_users.return_value = 3
            mock_count_by_group.return_value = {"group1": 2, "group2": 2, "group3": 2}

            result = daily_metrics_handler({}, lambda_context)

            # Verify both metric functions were called
            mock_count_users.assert_called_once()
            mock_count_by_group.assert_called_once()

            # Verify correct result was returned
            assert result == (3, {"group1": 2, "group2": 2, "group3": 2})

    def test_count_unique_users_exception_handling(self):
        """Test exception handling in count_unique_users_and_publish_metric.

        Expected: Should raise the exception after logging the error.
        """
        with patch("metrics.lambda_functions.metrics_table.scan") as mock_scan:
            mock_scan.side_effect = Exception("Test exception")

            # The exception is caught and logged, then re-raised with the original message
            with pytest.raises(Exception, match="Test exception"):
                count_unique_users_and_publish_metric()

    def test_count_users_by_group_exception_handling(self):
        """Test exception handling in count_users_by_group_and_publish_metric.

        Expected: Should raise the exception after logging the error.
        """
        with patch("metrics.lambda_functions.metrics_table.scan") as mock_scan:
            mock_scan.side_effect = Exception("Test exception")

            # The exception is caught and logged, then re-raised with the original message
            with pytest.raises(Exception, match="Test exception"):
                count_users_by_group_and_publish_metric()


class TestSQSEventProcessing:
    def test_process_metrics_sqs_event(self, dynamodb_table, lambda_context):
        """Test processing SQS events for user metrics.

        Expected: Should process multiple SQS records and call update_user_metrics for each.
        """
        # Create test SQS event
        sqs_event = {
            "Records": [
                {
                    "body": json.dumps(
                        {
                            "userId": "test-user-1",
                            "userGroups": ["group1", "group2"],
                            "messages": [
                                {"type": "human", "content": "Hello", "metadata": {"ragContext": "Some context"}},
                                {"type": "assistant", "content": "Hi there!"},
                            ],
                        }
                    )
                },
                {
                    "body": json.dumps(
                        {
                            "userId": "test-user-2",
                            "userGroups": ["group1"],
                            "messages": [
                                {"type": "human", "content": "Help me", "metadata": {}},
                                {"type": "assistant", "content": "How can I help?"},
                            ],
                        }
                    )
                },
            ]
        }

        with patch("metrics.lambda_functions.update_user_metrics") as mock_update_metrics:
            process_metrics_sqs_event(sqs_event, lambda_context)

            # Verify update_user_metrics was called correctly for each record
            assert mock_update_metrics.call_count == 2
            mock_update_metrics.assert_has_calls(
                [call("test-user-1", True, ["group1", "group2"]), call("test-user-2", False, ["group1"])]
            )

    def test_process_metrics_sqs_event_exception(self, lambda_context):
        """Test exception handling in process_metrics_sqs_event.

        Expected: Should log error and continue processing when SQS record has invalid JSON.
        """
        # Create test SQS event with bad JSON
        sqs_event = {"Records": [{"body": "invalid json"}]}

        # This shouldn't raise an exception, but should log an error
        with patch("metrics.lambda_functions.logger.error") as mock_logger:
            process_metrics_sqs_event(sqs_event, lambda_context)
            mock_logger.assert_called()

    def test_process_metrics_sqs_event_missing_userid(self, lambda_context):
        """Test handling of SQS messages missing userId.

        Expected: Should log error and continue processing when SQS record is missing userId.
        """
        # Create test SQS event with missing userId
        sqs_event = {"Records": [{"body": json.dumps({"userGroups": ["group1"], "messages": []})}]}

        with patch("metrics.lambda_functions.logger.error") as mock_logger:
            process_metrics_sqs_event(sqs_event, lambda_context)
            mock_logger.assert_called_with("SQS message missing required 'userId' field")


class TestCheckRagUsage:
    def test_check_rag_usage_with_rag_context(self):
        """Test check_rag_usage when RAG context is present.

        Expected: Should return True when ragContext is in message metadata.
        """
        messages = [
            {"type": "human", "content": "Hello", "metadata": {"ragContext": "Some context"}},
            {"type": "assistant", "content": "Hi there!"},
        ]

        result = check_rag_usage(messages)
        assert result is True

    def test_check_rag_usage_with_rag_documents(self):
        """Test check_rag_usage when RAG documents are present.

        Expected: Should return True when ragDocuments is in message metadata.
        """
        messages = [
            {"type": "human", "content": "Hello", "metadata": {"ragDocuments": ["doc1", "doc2"]}},
            {"type": "assistant", "content": "Hi there!"},
        ]

        result = check_rag_usage(messages)
        assert result is True

    def test_check_rag_usage_no_rag(self):
        """Test check_rag_usage when no RAG is used.

        Expected: Should return False when no RAG metadata is present.
        """
        messages = [
            {"type": "human", "content": "Hello", "metadata": {}},
            {"type": "assistant", "content": "Hi there!"},
        ]

        result = check_rag_usage(messages)
        assert result is False

    def test_check_rag_usage_empty_messages(self):
        """Test check_rag_usage with empty messages list.

        Expected: Should return False when messages list is empty.
        """
        result = check_rag_usage([])
        assert result is False

    def test_check_rag_usage_no_human_messages(self):
        """Test check_rag_usage with no human messages.

        Expected: Should return False when no human messages are present.
        """
        messages = [{"type": "assistant", "content": "Hi there!"}, {"type": "system", "content": "System message"}]

        result = check_rag_usage(messages)
        assert result is False

    def test_check_rag_usage_multiple_human_messages(self):
        """Test check_rag_usage with multiple human messages.

        Expected: Should return True if any human message has RAG metadata.
        """
        messages = [
            {"type": "human", "content": "First message", "metadata": {}},
            {"type": "assistant", "content": "Response"},
            {"type": "human", "content": "Second message", "metadata": {"ragContext": "Some context"}},
        ]

        result = check_rag_usage(messages)
        assert result is True


class TestUpdateUserMetrics:
    def test_update_user_metrics_new_user(self, dynamodb_table):
        """Test updating metrics for a new user.

        Expected: Should create a new user record with correct initial metrics.
        """
        with patch("metrics.lambda_functions.cloudwatch.put_metric_data") as mock_put_metric:
            update_user_metrics("new-test-user", True, ["group1", "group2"])

            # Check DynamoDB was updated correctly
            response = dynamodb_table.get_item(Key={"userId": "new-test-user"})
            assert "Item" in response
            assert response["Item"]["totalPrompts"] == 1
            assert response["Item"]["ragUsageCount"] == 1
            assert response["Item"]["userGroups"] == {"group1", "group2"}
            assert "firstSeen" in response["Item"]
            assert "lastSeen" in response["Item"]

            # Check CloudWatch metrics were published
            mock_put_metric.assert_called_once()
            args = mock_put_metric.call_args[1]
            assert args["Namespace"] == "LISA/UserMetrics"
            assert len(args["MetricData"]) == 4  # Total prompt, user prompt, RAG usage, user RAG usage

    def test_update_user_metrics_existing_user(self, dynamodb_table, sample_user_metrics):
        """Test updating metrics for an existing user.

        Expected: Should update existing user's metrics, incrementing totalPrompts but not ragUsageCount.
        """
        # Insert sample user first
        dynamodb_table.put_item(Item=sample_user_metrics)

        with patch("metrics.lambda_functions.cloudwatch.put_metric_data") as mock_put_metric:
            update_user_metrics("test-user-1", False, ["group3", "group4"])

            # Check DynamoDB was updated correctly
            response = dynamodb_table.get_item(Key={"userId": "test-user-1"})
            assert "Item" in response
            assert response["Item"]["totalPrompts"] == 11  # Increased by 1
            assert response["Item"]["ragUsageCount"] == 5  # No change (rag_usage was False)
            assert response["Item"]["userGroups"] == {"group3", "group4"}  # Updated groups

            # Check CloudWatch metrics were published
            mock_put_metric.assert_called_once()
            args = mock_put_metric.call_args[1]
            assert args["Namespace"] == "LISA/UserMetrics"
            assert len(args["MetricData"]) == 2  # Total prompt, user prompt (no RAG metrics)

    def test_update_user_metrics_existing_user_with_rag(self, dynamodb_table, sample_user_metrics):
        """Test updating metrics for an existing user with RAG usage.

        Expected: Should update existing user's metrics, incrementing both totalPrompts and ragUsageCount.
        """
        # Insert sample user first
        dynamodb_table.put_item(Item=sample_user_metrics)

        with patch("metrics.lambda_functions.cloudwatch.put_metric_data") as mock_put_metric:
            update_user_metrics("test-user-1", True, ["group1", "group2"])

            # Check DynamoDB was updated correctly
            response = dynamodb_table.get_item(Key={"userId": "test-user-1"})
            assert "Item" in response
            assert response["Item"]["totalPrompts"] == 11  # Increased by 1
            assert response["Item"]["ragUsageCount"] == 6  # Increased by 1
            assert response["Item"]["userGroups"] == {"group1", "group2"}  # Updated groups

            # Check CloudWatch metrics were published
            mock_put_metric.assert_called_once()
            args = mock_put_metric.call_args[1]
            assert args["Namespace"] == "LISA/UserMetrics"
            assert len(args["MetricData"]) == 4  # Total prompt, user prompt, RAG usage, user RAG usage

    def test_update_user_metrics_no_user_groups(self, dynamodb_table):
        """Test updating metrics with no user groups.

        Expected: Should create user record with no userGroups attribute when empty list provided.
        """
        update_user_metrics("new-test-user", False, [])

        # Check DynamoDB was updated correctly
        response = dynamodb_table.get_item(Key={"userId": "new-test-user"})
        assert "Item" in response
        assert response["Item"]["totalPrompts"] == 1
        assert response["Item"]["ragUsageCount"] == 0
        assert response["Item"].get("userGroups") is None  # No groups

    def test_update_user_metrics_client_error(self, dynamodb_table):
        """Test handling ClientError in update_user_metrics.

        Expected: Should catch and log the ClientError without raising it.
        """
        with patch("metrics.lambda_functions.metrics_table.get_item") as mock_get_item, patch(
            "metrics.lambda_functions.logger.error"
        ) as mock_logger:

            mock_get_item.side_effect = ClientError(
                {"Error": {"Code": "TestException", "Message": "Test error message"}}, "operation"
            )

            update_user_metrics("test-user-1", True, ["group1"])

            mock_logger.assert_called_with(ANY)  # We don't test the exact message as it may vary

    def test_update_user_metrics_cloudwatch_exception(self, dynamodb_table):
        """Test handling CloudWatch exceptions in update_user_metrics.

        Expected: Should catch and log CloudWatch exceptions without raising them.
        """
        with patch("metrics.lambda_functions.cloudwatch.put_metric_data") as mock_put_metric_data, patch(
            "metrics.lambda_functions.logger.error"
        ) as mock_logger:

            mock_put_metric_data.side_effect = Exception("Test CloudWatch exception")

            # This should not raise the exception
            update_user_metrics("test-user-1", True, ["group1"])

            mock_logger.assert_called_with("Failed to publish CloudWatch metrics: Test CloudWatch exception")
