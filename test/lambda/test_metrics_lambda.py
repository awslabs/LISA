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
os.environ["USAGE_METRICS_TABLE_NAME"] = "usage-metrics-table"


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
    """Create a mock DynamoDB table for usage metrics."""
    table = dynamodb.create_table(
        TableName="usage-metrics-table",
        KeySchema=[{"AttributeName": "userId", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "userId", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return table


@pytest.fixture
def sample_usage_metrics():
    """Sample usage metrics data."""
    return {
        "userId": "test-user-1",
        "totalPrompts": 10,
        "ragUsageCount": 5,
        "mcpToolCallsCount": 3,
        "mcpToolUsage": {"test_tool": 2, "another_tool": 1},
        "sessionMetrics": {
            "session-1": {
                "totalPrompts": 5,
                "ragUsage": 2,
                "mcpToolCallsCount": 1,
                "mcpToolUsage": {"test_tool": 1},
            },
            "session-2": {
                "totalPrompts": 5,
                "ragUsage": 3,
                "mcpToolCallsCount": 2,
                "mcpToolUsage": {"test_tool": 1, "another_tool": 1},
            },
        },
        "firstSeen": datetime.now().isoformat(),
        "lastSeen": datetime.now().isoformat(),
        "userGroups": {"group1", "group2"},
    }


@pytest.fixture
def multiple_usage_metrics(dynamodb_table):
    """Create multiple usage metrics entries."""
    items = [
        {
            "userId": "test-user-1",
            "totalPrompts": 10,
            "ragUsageCount": 5,
            "mcpToolCallsCount": 3,
            "mcpToolUsage": {"tool1": 2, "tool2": 1},
            "firstSeen": datetime.now().isoformat(),
            "lastSeen": datetime.now().isoformat(),
            "userGroups": {"group1", "group2"},
        },
        {
            "userId": "test-user-2",
            "totalPrompts": 20,
            "ragUsageCount": 10,
            "mcpToolCallsCount": 8,
            "mcpToolUsage": {"tool1": 5, "tool3": 3},
            "firstSeen": datetime.now().isoformat(),
            "lastSeen": datetime.now().isoformat(),
            "userGroups": {"group1", "group3"},
        },
        {
            "userId": "test-user-3",
            "totalPrompts": 5,
            "ragUsageCount": 2,
            "mcpToolCallsCount": 1,
            "mcpToolUsage": {"tool2": 1},
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
    },
).start()

# Patch the specific functions in utilities.common_functions
patch("utilities.common_functions.retry_config", retry_config).start()
patch("utilities.common_functions.api_wrapper", mock_api_wrapper).start()

# Also patch the api_wrapper in the metrics module specifically
patch("metrics.lambda_functions.api_wrapper", mock_api_wrapper).start()

# Module to test can be imported now that dependencies are mocked
from metrics.lambda_functions import (
    calculate_session_metrics,
    count_rag_usage,
    count_unique_users_and_publish_metric,
    count_users_by_group_and_publish_metric,
    daily_metrics_handler,
    get_user_metrics,
    get_user_metrics_all,
    process_metrics_sqs_event,
    publish_metric_deltas,
    update_user_metrics_by_session,
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
    def test_get_user_metrics_success(self, dynamodb_table, sample_usage_metrics, lambda_context):
        """Test getting usage metrics successfully.

        Expected: Should return usage metrics with 200 status code when userId exists.
        """
        # Insert sample data into table
        dynamodb_table.put_item(Item=sample_usage_metrics)

        # get usage metrics
        event = {"pathParameters": {"userId": "test-user-1"}}
        response = get_user_metrics(event, lambda_context)

        # Assert success
        assert response["statusCode"] == 200
        body = response["body"]
        assert body["test-user-1"]["totalPrompts"] == 10
        assert body["test-user-1"]["ragUsageCount"] == 5
        assert body["test-user-1"]["mcpToolCallsCount"] == 3
        assert body["test-user-1"]["mcpToolUsage"] == {"test_tool": 2, "another_tool": 1}
        assert set(body["test-user-1"]["userGroups"]) == {"group1", "group2"}
        assert "sessionMetrics" in body["test-user-1"]

    def test_get_user_metrics_missing_user_id(self, lambda_context):
        """Test getting usage metrics with missing userId parameter.

        Expected: Should return 400 status code when userId is missing from pathParameters.
        """
        event = {"pathParameters": {}}
        response = get_user_metrics(event, lambda_context)

        assert response["statusCode"] == 400
        assert "Missing userId" in json.loads(response["body"])["error"]

    def test_get_user_metrics_no_path_parameters(self, lambda_context):
        """Test getting usage metrics with no pathParameters.

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
        assert body["non-existent-user"]["mcpToolCallsCount"] == 0
        assert body["non-existent-user"]["mcpToolUsage"] == {}
        assert body["non-existent-user"]["userGroups"] == []
        assert body["non-existent-user"]["sessionMetrics"] == {}

    def test_get_user_metrics_exception_handling(self, lambda_context):
        """Test exception handling in get_user_metrics.

        Expected: Should return 500 status code when an exception occurs.
        """
        with patch("metrics.lambda_functions.usage_metrics_table.get_item") as mock_get_item:
            mock_get_item.side_effect = Exception("Test exception")

            event = {"pathParameters": {"userId": "test-user-1"}}
            response = get_user_metrics(event, lambda_context)

            assert response["statusCode"] == 500
            # The error message from the exception is passed through
            assert "Test exception" in json.loads(response["body"])["error"]


class TestGetUserMetricsAll:
    def test_get_user_metrics_all_success(self, dynamodb_table, multiple_usage_metrics, lambda_context):
        """Test getting all usage metrics successfully.

        Expected: Should return aggregated metrics across all users with correct calculations.
        """
        event = {}
        response = get_user_metrics_all(event, lambda_context)

        assert response["statusCode"] == 200
        body = response["body"]

        # Verify calculated metrics
        assert body["totalUniqueUsers"] == 3
        assert body["totalPrompts"] == 35  # Sum of all user prompts (10 + 20 + 5)
        assert body["totalRagUsage"] == 17  # Sum of all RAG usage (5 + 10 + 2)
        assert body["totalMCPToolCalls"] == 12  # Sum of all MCP tool calls (3 + 8 + 1)

        # Calculate expected percentages
        rag_percentage = float(body["ragUsagePercentage"])
        expected_rag_percentage = 17 / 35 * 100
        assert abs(rag_percentage - expected_rag_percentage) < 0.01

        mcp_percentage = float(body["mcpToolCallsPercentage"])
        expected_mcp_percentage = 12 / 35 * 100
        assert abs(mcp_percentage - expected_mcp_percentage) < 0.01

        # Verify user groups
        assert body["userGroups"]["group1"] == 2
        assert body["userGroups"]["group2"] == 2
        assert body["userGroups"]["group3"] == 2

        # Verify MCP tool usage aggregation
        assert body["mcpToolUsage"]["tool1"] == 7  # 2 + 5
        assert body["mcpToolUsage"]["tool2"] == 2  # 1 + 1
        assert body["mcpToolUsage"]["tool3"] == 3  # 3

    def test_get_user_metrics_all_empty_table(self, dynamodb_table, lambda_context):
        """Test getting all usage metrics from an empty table.

        Expected: Should return zero metrics when there are no users in the table.
        """
        event = {}
        response = get_user_metrics_all(event, lambda_context)

        assert response["statusCode"] == 200
        body = response["body"]

        assert body["totalUniqueUsers"] == 0
        assert body["totalPrompts"] == 0
        assert body["totalRagUsage"] == 0
        assert body["totalMCPToolCalls"] == 0
        assert body["ragUsagePercentage"] == 0
        assert body["mcpToolCallsPercentage"] == 0
        assert body["userGroups"] == {}
        assert body["mcpToolUsage"] == {}

    def test_get_user_metrics_all_exception_handling(self, lambda_context):
        """Test exception handling in get_user_metrics_all.

        Expected: Should return 500 status code when an exception occurs during metric retrieval.
        """
        with patch("metrics.lambda_functions.usage_metrics_table.scan") as mock_scan:
            mock_scan.side_effect = Exception("Test exception")

            event = {}
            response = get_user_metrics_all(event, lambda_context)

            assert response["statusCode"] == 500
            # The error message from the exception is passed through
            assert "Test exception" in json.loads(response["body"])["error"]


class TestCloudwatchMetrics:
    def test_count_unique_users_and_publish_metric(self, dynamodb_table, multiple_usage_metrics):
        """Test counting unique users and publishing to CloudWatch.

        Expected: Should count users correctly and publish metrics to CloudWatch.
        """
        with patch("metrics.lambda_functions.cloudwatch.put_metric_data") as mock_put_metric:
            result = count_unique_users_and_publish_metric()

            assert result == 3  # 3 users in test data

            # Verify CloudWatch was called correctly
            mock_put_metric.assert_called_once()
            args = mock_put_metric.call_args[1]
            assert args["Namespace"] == "LISA/UsageMetrics"
            assert len(args["MetricData"]) == 1
            assert args["MetricData"][0]["MetricName"] == "UniqueUsers"
            assert args["MetricData"][0]["Value"] == 3
            assert args["MetricData"][0]["Unit"] == "Count"

    def test_count_users_by_group_and_publish_metric(self, dynamodb_table, multiple_usage_metrics):
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
            assert args["Namespace"] == "LISA/UsageMetrics"
            assert len(args["MetricData"]) == 3  # 3 groups

            # Check that all groups have metrics
            metrics = {m["Dimensions"][0]["Value"]: m["Value"] for m in args["MetricData"]}
            assert metrics["group1"] == 2
            assert metrics["group2"] == 2
            assert metrics["group3"] == 2

    def test_daily_metrics_handler(self, dynamodb_table, multiple_usage_metrics, lambda_context):
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
        with patch("metrics.lambda_functions.usage_metrics_table.scan") as mock_scan:
            mock_scan.side_effect = Exception("Test exception")

            # The exception is caught and logged, then re-raised with the original message
            with pytest.raises(Exception, match="Test exception"):
                count_unique_users_and_publish_metric()

    def test_count_users_by_group_exception_handling(self):
        """Test exception handling in count_users_by_group_and_publish_metric.

        Expected: Should raise the exception after logging the error.
        """
        with patch("metrics.lambda_functions.usage_metrics_table.scan") as mock_scan:
            mock_scan.side_effect = Exception("Test exception")

            # The exception is caught and logged, then re-raised with the original message
            with pytest.raises(Exception, match="Test exception"):
                count_users_by_group_and_publish_metric()


class TestSQSEventProcessing:
    def test_process_metrics_sqs_event(self, dynamodb_table, lambda_context):
        """Test processing SQS events for usage metrics.

        Expected: Should process multiple SQS records and call update_user_metrics_by_session for each.
        """
        # Create test SQS event
        sqs_event = {
            "Records": [
                {
                    "body": json.dumps(
                        {
                            "userId": "test-user-1",
                            "sessionId": "session-1",
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
                            "sessionId": "session-2",
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

        with patch("metrics.lambda_functions.update_user_metrics_by_session") as mock_update_metrics:
            process_metrics_sqs_event(sqs_event, lambda_context)

            # Verify update_user_metrics_by_session was called correctly for each record
            assert mock_update_metrics.call_count == 2
            # Verify the calls included session metrics calculations
            assert mock_update_metrics.call_args_list[0][0][0] == "test-user-1"  # user_id
            assert mock_update_metrics.call_args_list[0][0][1] == "session-1"  # session_id
            assert mock_update_metrics.call_args_list[0][0][3] == ["group1", "group2"]  # user_groups

            assert mock_update_metrics.call_args_list[1][0][0] == "test-user-2"  # user_id
            assert mock_update_metrics.call_args_list[1][0][1] == "session-2"  # session_id
            assert mock_update_metrics.call_args_list[1][0][3] == ["group1"]  # user_groups

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

    def test_process_metrics_sqs_event_missing_sessionid(self, lambda_context):
        """Test handling of SQS messages missing sessionId.

        Expected: Should log error and continue processing when SQS record is missing sessionId.
        """
        # Create test SQS event with missing sessionId
        sqs_event = {
            "Records": [{"body": json.dumps({"userId": "test-user-1", "userGroups": ["group1"], "messages": []})}]
        }

        with patch("metrics.lambda_functions.logger.error") as mock_logger:
            process_metrics_sqs_event(sqs_event, lambda_context)
            mock_logger.assert_called_with("SQS message missing required 'sessionId' field")


class TestCountRagUsage:
    def test_count_rag_usage_with_file_context_direct_format(self):
        """Test count_rag_usage with 'File context:' in direct format messages.

        Expected: Should count occurrences of 'File context:' in human message content.
        """
        messages = [
            {"type": "human", "content": "File context: Some content here"},
            {"type": "assistant", "content": "Hi there!"},
        ]

        result = count_rag_usage(messages)
        assert result == 1

    def test_count_rag_usage_with_multiple_file_contexts(self):
        """Test count_rag_usage with multiple 'File context:' occurrences.

        Expected: Should count all occurrences of 'File context:' across all human messages.
        """
        messages = [
            {"type": "human", "content": "File context: First content\nFile context: Second content"},
            {"type": "assistant", "content": "Response"},
            {"type": "human", "content": "File context: Third content"},
        ]

        result = count_rag_usage(messages)
        assert result == 3

    def test_count_rag_usage_dynamodb_format(self):
        """Test count_rag_usage with DynamoDB format messages.

        Expected: Should handle DynamoDB format and count 'File context:' occurrences.
        """
        messages = [
            {
                "type": {"S": "human"},
                "content": {
                    "L": [
                        {
                            "M": {
                                "type": {"S": "text"},
                                "text": {"S": "File context: \nJmharold is the GOAT.\n\nJmharold is the GOAT.\n"},
                            }
                        },
                        {
                            "M": {
                                "type": {"S": "text"},
                                "text": {"S": "Can you tell me who jmharold is again one more time?"},
                            }
                        },
                    ]
                },
            }
        ]

        result = count_rag_usage(messages)
        assert result == 1

    def test_count_rag_usage_case_insensitive(self):
        """Test count_rag_usage is case insensitive.

        Expected: Should count 'FILE CONTEXT:', 'file context:', 'File Context:' etc.
        """
        messages = [
            {"type": "human", "content": "FILE CONTEXT: uppercase"},
            {"type": "human", "content": "file context: lowercase"},
            {"type": "human", "content": "File Context: mixed case"},
        ]

        result = count_rag_usage(messages)
        assert result == 3

    def test_count_rag_usage_no_file_context(self):
        """Test count_rag_usage when no 'File context:' is present.

        Expected: Should return 0 when no 'File context:' is found.
        """
        messages = [
            {"type": "human", "content": "Hello, no file context here", "metadata": {}},
            {"type": "assistant", "content": "Hi there!"},
        ]

        result = count_rag_usage(messages)
        assert result == 0

    def test_count_rag_usage_empty_messages(self):
        """Test count_rag_usage with empty messages list.

        Expected: Should return 0 when messages list is empty.
        """
        result = count_rag_usage([])
        assert result == 0

    def test_count_rag_usage_no_human_messages(self):
        """Test count_rag_usage with no human messages.

        Expected: Should return 0 when no human messages are present.
        """
        messages = [{"type": "assistant", "content": "Hi there!"}, {"type": "system", "content": "System message"}]

        result = count_rag_usage(messages)
        assert result == 0

    def test_count_rag_usage_content_list_format(self):
        """Test count_rag_usage with content as list format.

        Expected: Should handle content as list of objects with text fields.
        """
        messages = [
            {"type": "human", "content": [{"text": "File context: First part"}, {"text": "File context: Second part"}]}
        ]

        result = count_rag_usage(messages)
        assert result == 2


class TestUpdateUserMetricsBySession:
    def test_update_user_metrics_by_session_new_user(self, dynamodb_table):
        """Test updating session metrics for a new user.

        Expected: Should create a new user record with correct session metrics.
        """
        session_metrics = {
            "totalPrompts": 2,
            "ragUsage": 1,
            "mcpToolCallsCount": 0,
            "mcpToolUsage": {},
        }

        with patch("metrics.lambda_functions.publish_metric_deltas") as mock_publish_deltas:
            update_user_metrics_by_session("new-test-user", "session-1", session_metrics, ["group1", "group2"])

            # Check DynamoDB was updated correctly
            response = dynamodb_table.get_item(Key={"userId": "new-test-user"})
            assert "Item" in response
            assert response["Item"]["totalPrompts"] == 2
            assert response["Item"]["ragUsageCount"] == 1
            assert response["Item"]["mcpToolCallsCount"] == 0
            assert response["Item"]["userGroups"] == {"group1", "group2"}
            assert "firstSeen" in response["Item"]
            assert "lastSeen" in response["Item"]
            assert "sessionMetrics" in response["Item"]
            assert response["Item"]["sessionMetrics"]["session-1"] == session_metrics

            # Check that metric deltas were published
            mock_publish_deltas.assert_called_once()

    def test_update_user_metrics_by_session_multiple_sessions(self, dynamodb_table):
        """Test updating metrics with multiple sessions for aggregation.

        Expected: Should aggregate metrics across all sessions correctly.
        """
        # First session
        session_1_metrics = {
            "totalPrompts": 2,
            "ragUsage": 1,
            "mcpToolCallsCount": 3,
            "mcpToolUsage": {"tool1": 2, "tool2": 1},
        }

        # Second session
        session_2_metrics = {
            "totalPrompts": 3,
            "ragUsage": 2,
            "mcpToolCallsCount": 2,
            "mcpToolUsage": {"tool1": 1, "tool3": 1},
        }

        with patch("metrics.lambda_functions.publish_metric_deltas") as mock_publish_deltas:
            # Add first session
            update_user_metrics_by_session("test-user", "session-1", session_1_metrics, ["group1"])

            # Add second session
            update_user_metrics_by_session("test-user", "session-2", session_2_metrics, ["group1"])

            # Check final aggregated state
            response = dynamodb_table.get_item(Key={"userId": "test-user"})
            assert "Item" in response

            # Verify aggregated totals
            assert response["Item"]["totalPrompts"] == 5  # 2 + 3
            assert response["Item"]["ragUsageCount"] == 3  # 1 + 2
            assert response["Item"]["mcpToolCallsCount"] == 5  # 3 + 2
            assert response["Item"]["mcpToolUsage"]["tool1"] == 3  # 2 + 1
            assert response["Item"]["mcpToolUsage"]["tool2"] == 1  # 1 + 0
            assert response["Item"]["mcpToolUsage"]["tool3"] == 1  # 0 + 1

            # Verify session metrics are stored separately
            assert response["Item"]["sessionMetrics"]["session-1"] == session_1_metrics
            assert response["Item"]["sessionMetrics"]["session-2"] == session_2_metrics

            # Should have called publish_metric_deltas twice
            assert mock_publish_deltas.call_count == 2

    def test_update_user_metrics_by_session_delta_calculation(self, dynamodb_table):
        """Test that delta calculation works correctly for session updates.

        Expected: Should only publish deltas when session metrics change.
        """
        # Initial session metrics
        initial_metrics = {
            "totalPrompts": 2,
            "ragUsage": 1,
            "mcpToolCallsCount": 1,
            "mcpToolUsage": {"tool1": 1},
        }

        # Updated session metrics (same session, different values)
        updated_metrics = {
            "totalPrompts": 3,  # +1
            "ragUsage": 1,  # no change
            "mcpToolCallsCount": 2,  # +1
            "mcpToolUsage": {"tool1": 1, "tool2": 1},  # +1 tool2
        }

        with patch("metrics.lambda_functions.publish_metric_deltas") as mock_publish_deltas:
            # First update - should publish all values as deltas
            update_user_metrics_by_session("test-user", "session-1", initial_metrics, ["group1"])

            first_call_args = mock_publish_deltas.call_args[0]
            assert first_call_args[1] == 2  # delta_prompts
            assert first_call_args[2] == 1  # delta_rag
            assert first_call_args[3] == 1  # delta_mcp_calls
            assert first_call_args[4] == {"tool1": 1}  # delta_mcp_usage

            # Second update - should only publish the differences
            update_user_metrics_by_session("test-user", "session-1", updated_metrics, ["group1"])

            second_call_args = mock_publish_deltas.call_args[0]
            assert second_call_args[1] == 1  # delta_prompts (+1)
            assert second_call_args[2] == 0  # delta_rag (no change)
            assert second_call_args[3] == 1  # delta_mcp_calls (+1)
            assert second_call_args[4] == {"tool2": 1}  # only new tool usage

    def test_update_user_metrics_by_session_no_table_name(self):
        """Test handling when USAGE_METRICS_TABLE_NAME environment variable is missing.

        Expected: Should return early without processing when table name is not set.
        """
        with patch.dict(os.environ, {}, clear=True):
            # Should not raise an exception, just return early
            update_user_metrics_by_session("test-user", "session-1", {}, [])
            # If this doesn't raise an exception, the test passes

    def test_update_user_metrics_by_session_exception_handling(self, dynamodb_table):
        """Test exception handling in update_user_metrics_by_session.

        Expected: Should log error when DynamoDB operations fail.
        """
        session_metrics = {
            "totalPrompts": 1,
            "ragUsage": 0,
            "mcpToolCallsCount": 0,
            "mcpToolUsage": {},
        }

        with patch("metrics.lambda_functions.usage_metrics_table.get_item") as mock_get_item, patch(
            "metrics.lambda_functions.logger.error"
        ) as mock_logger:

            mock_get_item.side_effect = ClientError(
                error_response={"Error": {"Code": "ResourceNotFoundException", "Message": "Table not found"}},
                operation_name="GetItem",
            )

            # Should not raise exception
            update_user_metrics_by_session("test-user", "session-1", session_metrics, [])

            # Should log the error
            mock_logger.assert_called()
            assert "Failed to update session metrics" in str(mock_logger.call_args)


class TestCalculateSessionMetrics:
    def test_calculate_session_metrics_empty_messages(self):
        """Test calculate_session_metrics with empty message list.

        Expected: Should return zero metrics when messages list is empty.
        """
        result = calculate_session_metrics([])

        assert result["totalPrompts"] == 0
        assert result["ragUsage"] == 0
        assert result["mcpToolCallsCount"] == 0
        assert result["mcpToolUsage"] == {}

    def test_calculate_session_metrics_basic_messages(self):
        """Test calculate_session_metrics with basic human and assistant messages.

        Expected: Should count human messages as prompts and count 'File context:' occurrences for RAG usage.
        """
        messages = [
            {
                "type": "human",
                "content": "Hello",
                "metadata": {},
            },
            {"type": "assistant", "content": "Hi there!"},
            {"type": "human", "content": "File context: Some content here\nHow are you?"},
            {"type": "assistant", "content": "I'm doing well!"},
        ]

        result = calculate_session_metrics(messages)

        assert result["totalPrompts"] == 2  # Two human messages
        assert result["ragUsage"] == 1  # One "File context:" occurrence
        assert result["mcpToolCallsCount"] == 0
        assert result["mcpToolUsage"] == {}

    def test_calculate_session_metrics_with_mcp_tools_direct_format(self):
        """Test calculate_session_metrics with MCP tool calls in direct format.

        Expected: Should count MCP tool calls and track individual tool usage.
        """
        messages = [
            {
                "type": "human",
                "content": "Use some tools",
                "metadata": {},
                "toolCalls": [
                    {"type": "tool_call", "name": "search_tool"},
                    {"type": "tool_call", "name": "calculator"},
                    {"type": "tool_call", "name": "search_tool"},
                ],
            },
            {"type": "assistant", "content": "Tools executed"},
        ]

        result = calculate_session_metrics(messages)

        assert result["totalPrompts"] == 1
        assert result["ragUsage"] == 0
        assert result["mcpToolCallsCount"] == 3
        assert result["mcpToolUsage"]["search_tool"] == 2
        assert result["mcpToolUsage"]["calculator"] == 1

    def test_calculate_session_metrics_with_mcp_tools_dynamodb_format(self):
        """Test calculate_session_metrics with MCP tool calls in DynamoDB format.

        Expected: Should handle DynamoDB format tool calls correctly.
        """
        messages = [
            {
                "type": {"S": "human"},
                "content": {"S": "Use some tools"},
                "toolCalls": {
                    "L": [
                        {
                            "M": {
                                "type": {"S": "tool_call"},
                                "name": {"S": "file_reader"},
                            }
                        },
                        {
                            "M": {
                                "type": {"S": "tool_call"},
                                "name": {"S": "web_scraper"},
                            }
                        },
                    ]
                },
            }
        ]

        result = calculate_session_metrics(messages)

        assert result["totalPrompts"] == 1
        assert result["ragUsage"] == 0
        assert result["mcpToolCallsCount"] == 2
        assert result["mcpToolUsage"]["file_reader"] == 1
        assert result["mcpToolUsage"]["web_scraper"] == 1

    def test_calculate_session_metrics_mixed_formats(self):
        """Test calculate_session_metrics with mixed message formats.

        Expected: Should handle both direct and DynamoDB formats in same session.
        """
        messages = [
            {
                "type": "human",
                "content": "File context: Some content\nDirect format message",
                "metadata": {"ragDocuments": ["doc1"]},
                "toolCalls": [{"type": "tool_call", "name": "direct_tool"}],
            },
            {
                "type": {"S": "human"},
                "content": {"S": "DynamoDB format message"},
                "toolCalls": {
                    "L": [
                        {
                            "M": {
                                "type": {"S": "tool_call"},
                                "name": {"S": "dynamo_tool"},
                            }
                        }
                    ]
                },
            },
        ]

        result = calculate_session_metrics(messages)

        assert result["totalPrompts"] == 2
        assert result["ragUsage"] == 1  # One "File context:" occurrence in first message
        assert result["mcpToolCallsCount"] == 2
        assert result["mcpToolUsage"]["direct_tool"] == 1
        assert result["mcpToolUsage"]["dynamo_tool"] == 1


class TestPublishMetricDeltas:
    def test_publish_metric_deltas_no_changes(self):
        """Test publish_metric_deltas when no metrics changed.

        Expected: Should not publish any metrics when all deltas are zero.
        """
        with patch("metrics.lambda_functions.cloudwatch.put_metric_data") as mock_put_metric:
            publish_metric_deltas("test-user", 0, 0, 0, {}, ["group1"])

            # Should not call CloudWatch when no changes
            mock_put_metric.assert_not_called()

    def test_publish_metric_deltas_prompt_changes_only(self):
        """Test publish_metric_deltas with only prompt count changes.

        Expected: Should publish only prompt-related metrics.
        """
        with patch("metrics.lambda_functions.cloudwatch.put_metric_data") as mock_put_metric:
            publish_metric_deltas("test-user", 5, 0, 0, {}, ["group1", "group2"])

            mock_put_metric.assert_called_once()
            args = mock_put_metric.call_args[1]
            assert args["Namespace"] == "LISA/UsageMetrics"

            # Should have prompt metrics + group metrics
            metric_names = [m["MetricName"] for m in args["MetricData"]]
            assert "TotalPromptCount" in metric_names
            assert "UserPromptCount" in metric_names
            assert "GroupPromptCount" in metric_names
            assert "RAGUsageCount" not in metric_names
            assert "TotalMCPToolCalls" not in metric_names

            # Check group metrics are published for both groups
            group_metrics = [m for m in args["MetricData"] if m["MetricName"] == "GroupPromptCount"]
            assert len(group_metrics) == 2
            group_names = [m["Dimensions"][0]["Value"] for m in group_metrics]
            assert "group1" in group_names
            assert "group2" in group_names

    def test_publish_metric_deltas_all_changes(self):
        """Test publish_metric_deltas with all types of changes.

        Expected: Should publish all relevant metrics including individual tool metrics.
        """
        delta_mcp_usage = {"tool1": 2, "tool2": -1, "tool3": 3}
        user_groups = ["group1"]

        with patch("metrics.lambda_functions.cloudwatch.put_metric_data") as mock_put_metric:
            publish_metric_deltas("test-user", 3, 1, 2, delta_mcp_usage, user_groups)

            mock_put_metric.assert_called_once()
            args = mock_put_metric.call_args[1]
            metric_names = [m["MetricName"] for m in args["MetricData"]]

            # Check all main metric types are present
            assert "TotalPromptCount" in metric_names
            assert "UserPromptCount" in metric_names
            assert "RAGUsageCount" in metric_names
            assert "UserRAGUsageCount" in metric_names
            assert "TotalMCPToolCalls" in metric_names
            assert "UserMCPToolCalls" in metric_names
            assert "MCPToolCallsByTool" in metric_names
            assert "GroupPromptCount" in metric_names
            assert "GroupRAGUsageCount" in metric_names
            assert "GroupMCPToolCalls" in metric_names

            # Check individual tool metrics
            tool_metrics = [m for m in args["MetricData"] if m["MetricName"] == "MCPToolCallsByTool"]
            assert len(tool_metrics) == 3  # tool1, tool2, tool3
            tool_values = {m["Dimensions"][0]["Value"]: m["Value"] for m in tool_metrics}
            assert tool_values["tool1"] == 2
            assert tool_values["tool2"] == -1
            assert tool_values["tool3"] == 3

    def test_publish_metric_deltas_exception_handling(self):
        """Test publish_metric_deltas exception handling.

        Expected: Should log error and not raise exception when CloudWatch fails.
        """
        with patch("metrics.lambda_functions.cloudwatch.put_metric_data") as mock_put_metric, patch(
            "metrics.lambda_functions.logger.error"
        ) as mock_logger:

            mock_put_metric.side_effect = Exception("CloudWatch error")

            # Should not raise exception
            publish_metric_deltas("test-user", 1, 0, 0, {}, [])

            mock_logger.assert_called_with("Failed to publish metric deltas: CloudWatch error")
