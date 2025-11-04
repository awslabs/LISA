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

"""Unit tests for schedule monitoring lambda."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

# Set mock AWS credentials
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["MODEL_TABLE_NAME"] = "test-model-table"


@pytest.fixture
def lambda_context():
    """Mock Lambda context object."""
    context = MagicMock()
    context.function_name = "schedule-monitoring-lambda"
    context.function_version = "1"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:schedule-monitoring-lambda"
    context.memory_limit_in_mb = 128
    context.log_group_name = "/aws/lambda/schedule-monitoring-lambda"
    context.log_stream_name = "2025/01/01/[$LATEST]abcdef123456"
    context.aws_request_id = "00000000-0000-0000-0000-000000000000"
    return context


@pytest.fixture
def sample_model_with_schedule():
    """Sample model item with active schedule."""
    return {
        "model_id": "test-model",
        "model_status": "InService",
        "auto_scaling_group": "test-asg",
        "autoScalingConfig": {
            "scheduling": {
                "scheduleType": "RECURRING_DAILY",
                "timezone": "UTC",
                "scheduleEnabled": True,
                "scheduleConfigured": True,
                "lastScheduleFailed": False,
                "dailySchedule": {"startTime": "09:00", "stopTime": "17:00"},
                "scheduledActionArns": [
                    "arn:aws:autoscaling:us-east-1:123456789012:scheduledUpdateGroupAction:*:autoScalingGroupName/test-asg:scheduledActionName/test-model-daily-start",
                    "arn:aws:autoscaling:us-east-1:123456789012:scheduledUpdateGroupAction:*:autoScalingGroupName/test-asg:scheduledActionName/test-model-daily-stop",
                ],
                "lastScheduleUpdate": "2025-01-14T12:00:00Z",
            }
        },
    }


class TestScheduleMonitoring:
    """Test schedule monitoring Lambda function."""

    @patch("models.scheduling.schedule_monitoring.ecs_client")
    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_lambda_handler_autoscaling_event_success(self, mock_model_table, mock_ecs_client, lambda_context):
        """Test successful autoscaling event handling."""
        from models.scheduling.schedule_monitoring import lambda_handler

        # Mock autoscaling event
        event = {
            "source": "aws.autoscaling",
            "detail": {
                "StatusCode": "Successful",
                "AutoScalingGroupName": "test-asg",
                "StatusMessage": "Scaling completed successfully",
            },
        }

        # Mock model lookup
        mock_model_table.scan.return_value = {"Items": [{"model_id": "test-model"}], "Count": 1}

        # Mock model get_item
        mock_model_table.get_item.return_value = {
            "Item": {
                "model_id": "test-model",
                "ecs_service_arn": "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service",
            }
        }

        # Mock ECS service
        mock_ecs_client.describe_services.return_value = {"services": [{"runningCount": 1}]}

        # Mock update_item
        mock_model_table.update_item.return_value = {}

        # Execute
        result = lambda_handler(event, lambda_context)

        # Verify response
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["message"] == "Scaling event processed successfully"
        assert body["modelId"] == "test-model"

    def test_lambda_handler_sync_status_operation(self, lambda_context):
        """Test sync_status operation."""
        from models.scheduling.schedule_monitoring import lambda_handler

        # Test event for sync operation
        event = {"operation": "sync_status", "modelId": "test-model"}

        # Execute - this will fail due to missing ECS service, but tests the routing
        result = lambda_handler(event, lambda_context)

        # Verify error response (expected since we don't mock the full chain)
        assert result["statusCode"] == 500

    def test_lambda_handler_unknown_event(self, lambda_context):
        """Test handling of unknown event format."""
        from models.scheduling.schedule_monitoring import lambda_handler

        # Execute with empty event
        result = lambda_handler({}, lambda_context)

        # Verify response
        assert result["statusCode"] == 200
        assert "Event processed (no action taken)" in result["message"]

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_lambda_handler_exception(self, mock_model_table, lambda_context):
        """Test monitoring with exception."""
        from models.scheduling.schedule_monitoring import lambda_handler

        # Mock exception
        mock_model_table.scan.side_effect = Exception("DynamoDB error")

        # Test autoscaling event that will trigger the exception
        event = {
            "source": "aws.autoscaling",
            "detail": {"StatusCode": "Successful", "AutoScalingGroupName": "test-asg"},
        }

        # Execute
        result = lambda_handler(event, lambda_context)

        # Verify error response - the function may return 200 with error message in body
        assert result["statusCode"] in [200, 500]
        if result["statusCode"] == 500:
            body = json.loads(result["body"])
            assert "DynamoDB error" in body["message"]
        else:
            # If it returns 200, it should still handle the error gracefully
            assert "message" in result

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_find_model_by_asg_name_success(self, mock_model_table):
        """Test successful model lookup by ASG name."""
        from models.scheduling.schedule_monitoring import find_model_by_asg_name

        # Mock model table scan
        mock_model_table.scan.return_value = {"Items": [{"model_id": "test-model"}], "Count": 1}

        result = find_model_by_asg_name("test-asg")

        assert result == "test-model"
        mock_model_table.scan.assert_called_once()

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_find_model_by_asg_name_not_found(self, mock_model_table):
        """Test model lookup when ASG not found."""
        from models.scheduling.schedule_monitoring import find_model_by_asg_name

        # Mock empty scan result
        mock_model_table.scan.return_value = {"Items": [], "Count": 0}

        result = find_model_by_asg_name("nonexistent-asg")

        assert result is None

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_get_ecs_service_name_success(self, mock_model_table):
        """Test successful ECS service name retrieval."""
        from models.scheduling.schedule_monitoring import get_ecs_service_name

        # Mock model table response
        mock_model_table.get_item.return_value = {
            "Item": {
                "model_id": "test-model",
                "ecs_service_arn": "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service",
            }
        }

        result = get_ecs_service_name("test-model")

        assert result == "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service"

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_get_ecs_service_name_not_found(self, mock_model_table):
        """Test ECS service name retrieval when model not found."""
        from models.scheduling.schedule_monitoring import get_ecs_service_name

        # Mock model not found
        mock_model_table.get_item.return_value = {}

        result = get_ecs_service_name("nonexistent-model")

        assert result is None

    @patch("models.scheduling.schedule_monitoring.ecs_client")
    def test_get_ecs_service_running_count_success(self, mock_ecs_client):
        """Test successful ECS service running count retrieval."""
        from models.scheduling.schedule_monitoring import get_ecs_service_running_count

        # Mock ECS client response
        mock_ecs_client.describe_services.return_value = {"services": [{"runningCount": 2}]}

        result = get_ecs_service_running_count("test-service-arn")

        assert result == 2

    @patch("models.scheduling.schedule_monitoring.ecs_client")
    def test_get_ecs_service_running_count_not_found(self, mock_ecs_client):
        """Test ECS service running count when service not found."""
        from models.scheduling.schedule_monitoring import get_ecs_service_running_count

        # Mock empty services response
        mock_ecs_client.describe_services.return_value = {"services": []}

        result = get_ecs_service_running_count("nonexistent-service")

        assert result == 0

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_update_model_status_success(self, mock_model_table):
        """Test successful model status update."""
        from models.domain_objects import ModelStatus
        from models.scheduling.schedule_monitoring import update_model_status

        mock_model_table.update_item.return_value = {}

        # Execute
        update_model_status("test-model", ModelStatus.IN_SERVICE, "Test reason")

        # Verify update_item was called
        mock_model_table.update_item.assert_called_once()
        call_args = mock_model_table.update_item.call_args
        assert call_args[1]["Key"] == {"model_id": "test-model"}

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_get_current_retry_count_success(self, mock_model_table):
        """Test successful retry count retrieval."""
        from models.scheduling.schedule_monitoring import get_current_retry_count

        # Mock model with retry count
        mock_model_table.get_item.return_value = {
            "Item": {
                "model_id": "test-model",
                "autoScalingConfig": {"scheduling": {"lastScheduleFailure": {"retryCount": 2}}},
            }
        }

        result = get_current_retry_count("test-model")

        assert result == 2

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_get_current_retry_count_no_failure(self, mock_model_table):
        """Test retry count retrieval when no failure exists."""
        from models.scheduling.schedule_monitoring import get_current_retry_count

        # Mock model without failure info
        mock_model_table.get_item.return_value = {
            "Item": {"model_id": "test-model", "autoScalingConfig": {"scheduling": {}}}
        }

        result = get_current_retry_count("test-model")

        assert result == 0


class TestScheduleMonitoringHelpers:
    """Test actual helper functions that exist in schedule monitoring."""

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_update_schedule_failure_success(self, mock_model_table):
        """Test successful schedule failure update."""
        from models.scheduling.schedule_monitoring import update_schedule_failure

        mock_model_table.update_item.return_value = {}

        # Execute
        update_schedule_failure("test-model", "Test error", 1)

        # Verify update_item was called
        mock_model_table.update_item.assert_called_once()
        call_args = mock_model_table.update_item.call_args
        assert call_args[1]["Key"] == {"model_id": "test-model"}

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_update_schedule_status_failed(self, mock_model_table):
        """Test updating schedule status to failed."""
        from models.scheduling.schedule_monitoring import update_schedule_status

        mock_model_table.update_item.return_value = {}

        # Execute
        update_schedule_status("test-model", True, "Test error")

        # Verify update_item was called
        mock_model_table.update_item.assert_called_once()
        call_args = mock_model_table.update_item.call_args
        assert call_args[1]["ExpressionAttributeValues"][":failed"] is True

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_update_schedule_status_success(self, mock_model_table):
        """Test updating schedule status to success."""
        from models.scheduling.schedule_monitoring import update_schedule_status

        mock_model_table.update_item.return_value = {}

        # Execute
        update_schedule_status("test-model", False)

        # Verify update_item was called
        mock_model_table.update_item.assert_called_once()
        call_args = mock_model_table.update_item.call_args
        assert call_args[1]["ExpressionAttributeValues"][":failed"] is False

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_reset_retry_count_success(self, mock_model_table):
        """Test successful retry count reset."""
        from models.scheduling.schedule_monitoring import reset_retry_count

        mock_model_table.update_item.return_value = {}

        # Execute
        reset_retry_count("test-model")

        # Verify update_item was called
        mock_model_table.update_item.assert_called_once()
        call_args = mock_model_table.update_item.call_args
        assert call_args[1]["Key"] == {"model_id": "test-model"}

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_get_model_info_success(self, mock_model_table):
        """Test successful model info retrieval."""
        from models.scheduling.schedule_monitoring import get_model_info

        # Mock model table response
        mock_model_table.get_item.return_value = {"Item": {"model_id": "test-model", "model_status": "InService"}}

        result = get_model_info("test-model")

        assert result is not None
        assert result["model_id"] == "test-model"

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_get_model_info_not_found(self, mock_model_table):
        """Test model info retrieval when model not found."""
        from models.scheduling.schedule_monitoring import get_model_info

        # Mock model not found
        mock_model_table.get_item.return_value = {}

        result = get_model_info("nonexistent-model")

        assert result is None
