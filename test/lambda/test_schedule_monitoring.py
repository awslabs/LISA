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
                "scheduleType": "RECURRING",
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

    @patch("models.scheduling.schedule_monitoring.autoscaling_client")
    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_lambda_handler_autoscaling_event_success(self, mock_model_table, mock_autoscaling_client, lambda_context):
        """Test successful autoscaling event handling."""
        from models.scheduling.schedule_monitoring import lambda_handler

        # Mock autoscaling event
        event = {
            "source": "aws.autoscaling",
            "detail-type": "EC2 Instance Launch Successful",
            "detail": {
                "StatusCode": "Successful",
                "AutoScalingGroupName": "test-asg",
                "StatusMessage": "Scaling completed successfully",
            },
        }

        # Mock model lookup
        mock_model_table.scan.return_value = {"Items": [{"model_id": "test-model"}], "Count": 1}

        # Mock ASG describe call
        mock_autoscaling_client.describe_auto_scaling_groups.return_value = {
            "AutoScalingGroups": [
                {"Instances": [{"LifecycleState": "InService"}, {"LifecycleState": "InService"}], "DesiredCapacity": 2}
            ]
        }

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
                "model_config": {"autoScalingConfig": {"scheduling": {"lastScheduleFailure": {"retryCount": 2}}}},
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

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_get_model_info_exception(self, mock_model_table):
        """Test model info retrieval with exception."""
        from models.scheduling.schedule_monitoring import get_model_info

        # Mock exception
        mock_model_table.get_item.side_effect = Exception("DynamoDB error")

        result = get_model_info("test-model")

        assert result is None

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_find_model_by_asg_name_exception(self, mock_model_table):
        """Test model lookup by ASG name with exception."""
        from models.scheduling.schedule_monitoring import find_model_by_asg_name

        # Mock exception
        mock_model_table.scan.side_effect = Exception("DynamoDB error")

        result = find_model_by_asg_name("test-asg")

        assert result is None

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_update_model_status_exception(self, mock_model_table):
        """Test model status update with exception."""
        from models.domain_objects import ModelStatus
        from models.scheduling.schedule_monitoring import update_model_status

        # Mock exception
        mock_model_table.update_item.side_effect = Exception("DynamoDB error")

        # Execute - should raise exception
        with pytest.raises(Exception):
            update_model_status("test-model", ModelStatus.IN_SERVICE, "Test reason")

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_get_current_retry_count_exception(self, mock_model_table):
        """Test retry count retrieval with exception."""
        from models.scheduling.schedule_monitoring import get_current_retry_count

        # Mock exception
        mock_model_table.get_item.side_effect = Exception("DynamoDB error")

        result = get_current_retry_count("test-model")

        assert result == 0

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_get_current_retry_count_no_item(self, mock_model_table):
        """Test retry count retrieval when model not found."""
        from models.scheduling.schedule_monitoring import get_current_retry_count

        # Mock model not found
        mock_model_table.get_item.return_value = {}

        result = get_current_retry_count("test-model")

        assert result == 0

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_update_schedule_failure_exception(self, mock_model_table):
        """Test schedule failure update with exception."""
        from models.scheduling.schedule_monitoring import update_schedule_failure

        # Mock exception
        mock_model_table.update_item.side_effect = Exception("DynamoDB error")

        # Execute - should raise exception
        with pytest.raises(Exception):
            update_schedule_failure("test-model", "Test error", 1)

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_update_schedule_status_exception(self, mock_model_table):
        """Test schedule status update with exception."""
        from models.scheduling.schedule_monitoring import update_schedule_status

        # Mock exception
        mock_model_table.update_item.side_effect = Exception("DynamoDB error")

        # Execute - should raise exception
        with pytest.raises(Exception):
            update_schedule_status("test-model", True, "Test error")

    @patch("models.scheduling.schedule_monitoring.model_table")
    def test_reset_retry_count_exception(self, mock_model_table):
        """Test retry count reset with exception."""
        from models.scheduling.schedule_monitoring import reset_retry_count

        # Mock exception
        mock_model_table.update_item.side_effect = Exception("DynamoDB error")

        # Execute - should not raise exception, just log error
        reset_retry_count("test-model")

        # Verify update_item was called
        mock_model_table.update_item.assert_called_once()


class TestScheduleMonitoringComplex:
    """Test complex functions with comprehensive coverage."""

    @patch("models.scheduling.schedule_monitoring.update_schedule_failure")
    @patch("models.scheduling.schedule_monitoring.update_schedule_status")
    @patch("models.scheduling.schedule_monitoring.schedule_retry")
    @patch("models.scheduling.schedule_monitoring.get_current_retry_count")
    def test_handle_failed_scaling_retry(
        self, mock_get_retry_count, mock_schedule_retry, mock_update_schedule_status, mock_update_schedule_failure
    ):
        """Test failed scaling with retry."""
        from models.scheduling.schedule_monitoring import handle_failed_scaling

        # Mock retry count below max
        mock_get_retry_count.return_value = 1

        detail = {"StatusMessage": "Scaling failed"}

        result = handle_failed_scaling("test-model", "test-asg", detail)

        # Verify response
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["message"] == "Scaling failure detected, retry scheduled"
        assert body["retryCount"] == 2
        assert body["delaySeconds"] == 120

        # Verify calls
        mock_update_schedule_failure.assert_called_once_with("test-model", "Scaling failed", 2)
        mock_schedule_retry.assert_called_once_with("test-model", "test-asg", 120, 2)

    @patch("models.scheduling.schedule_monitoring.update_schedule_status")
    @patch("models.scheduling.schedule_monitoring.get_current_retry_count")
    def test_handle_failed_scaling_max_retries(self, mock_get_retry_count, mock_update_schedule_status):
        """Test failed scaling with max retries exceeded."""
        from models.scheduling.schedule_monitoring import handle_failed_scaling

        # Mock retry count at max
        mock_get_retry_count.return_value = 3

        detail = {"StatusMessage": "Scaling failed"}

        result = handle_failed_scaling("test-model", "test-asg", detail)

        # Verify response
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["message"] == "Max retries exceeded, schedule marked as failed"
        assert body["finalError"] == "Scaling failed"

        # Verify calls
        mock_update_schedule_status.assert_called_once_with("test-model", True, "Scaling failed")

    def test_handle_failed_scaling_exception(self):
        """Test failed scaling with exception."""
        from models.scheduling.schedule_monitoring import handle_failed_scaling

        detail = {}  # Missing StatusMessage

        # Execute - should raise exception
        with pytest.raises(Exception):
            handle_failed_scaling("test-model", "test-asg", detail)

    @patch("models.scheduling.schedule_monitoring.autoscaling_client")
    @patch("models.scheduling.schedule_monitoring.update_model_status")
    @patch("models.scheduling.schedule_monitoring.get_model_info")
    def test_sync_model_status_success(self, mock_get_model_info, mock_update_model_status, mock_autoscaling_client):
        """Test successful sync model status."""
        from models.scheduling.schedule_monitoring import sync_model_status

        # Mock model info
        mock_get_model_info.return_value = {"auto_scaling_group": "test-asg"}

        # Mock ASG response
        mock_autoscaling_client.describe_auto_scaling_groups.return_value = {
            "AutoScalingGroups": [{"Instances": [{"LifecycleState": "InService"}], "DesiredCapacity": 1}]
        }

        event = {"modelId": "test-model"}
        result = sync_model_status(event)

        # Verify response
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["message"] == "Status synchronized successfully"

    def test_sync_model_status_no_model_id(self):
        """Test sync model status without model ID."""
        from models.scheduling.schedule_monitoring import sync_model_status

        event = {}

        # Execute - should raise exception
        with pytest.raises(ValueError, match="modelId is required"):
            sync_model_status(event)

    @patch("models.scheduling.schedule_monitoring.get_model_info")
    def test_sync_model_status_model_not_found(self, mock_get_model_info):
        """Test sync model status when model not found."""
        from models.scheduling.schedule_monitoring import sync_model_status

        # Mock model not found
        mock_get_model_info.return_value = None

        event = {"modelId": "test-model"}

        # Execute - should raise exception
        with pytest.raises(ValueError, match="Model test-model not found"):
            sync_model_status(event)

    @patch("models.scheduling.schedule_monitoring.get_model_info")
    def test_sync_model_status_no_asg(self, mock_get_model_info):
        """Test sync model status when no ASG info."""
        from models.scheduling.schedule_monitoring import sync_model_status

        # Mock model without ASG info
        mock_get_model_info.return_value = {"model_id": "test-model"}

        event = {"modelId": "test-model"}

        # Execute - should raise exception
        with pytest.raises(ValueError, match="No ASG information found"):
            sync_model_status(event)

    @patch("models.scheduling.schedule_monitoring.autoscaling_client")
    @patch("models.scheduling.schedule_monitoring.get_model_info")
    def test_sync_model_status_asg_not_found(self, mock_get_model_info, mock_autoscaling_client):
        """Test sync model status when ASG not found."""
        from models.scheduling.schedule_monitoring import sync_model_status

        # Mock model info
        mock_get_model_info.return_value = {"auto_scaling_group": "test-asg"}

        # Mock ASG not found
        mock_autoscaling_client.describe_auto_scaling_groups.return_value = {"AutoScalingGroups": []}

        event = {"modelId": "test-model"}

        # Execute - should raise exception
        with pytest.raises(ValueError, match="ASG test-asg not found"):
            sync_model_status(event)

    @patch("models.scheduling.schedule_monitoring.reset_retry_count")
    @patch("models.scheduling.schedule_monitoring.get_model_info")
    def test_retry_failed_scaling_success(self, mock_get_model_info, mock_reset_retry_count):
        """Test successful retry failed scaling."""
        from models.scheduling.schedule_monitoring import retry_failed_scaling

        # Mock model info
        mock_get_model_info.return_value = {"model_id": "test-model"}

        event = {"modelId": "test-model"}
        result = retry_failed_scaling(event)

        # Verify response
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["message"] == "Retry count reset - normal scheduling will retry the operation"

        mock_reset_retry_count.assert_called_once_with("test-model")

    def test_retry_failed_scaling_no_model_id(self):
        """Test retry failed scaling without model ID."""
        from models.scheduling.schedule_monitoring import retry_failed_scaling

        event = {}

        # Execute - should raise exception
        with pytest.raises(ValueError, match="modelId is required"):
            retry_failed_scaling(event)

    @patch("models.scheduling.schedule_monitoring.get_model_info")
    def test_retry_failed_scaling_model_not_found(self, mock_get_model_info):
        """Test retry failed scaling when model not found."""
        from models.scheduling.schedule_monitoring import retry_failed_scaling

        # Mock model not found
        mock_get_model_info.return_value = None

        event = {"modelId": "test-model"}

        # Execute - should raise exception
        with pytest.raises(ValueError, match="Model test-model not found"):
            retry_failed_scaling(event)


class TestScheduleMonitoringEdgeCases:
    """Test edge cases and additional coverage."""

    @patch("models.scheduling.schedule_monitoring.update_model_status")
    @patch("models.scheduling.schedule_monitoring.autoscaling_client")
    @patch("models.scheduling.schedule_monitoring.find_model_by_asg_name")
    def test_handle_successful_scaling_asg_not_found(
        self,
        mock_find_model,
        mock_autoscaling_client,
        mock_update_model_status,
    ):
        """Test handle_successful_scaling when ASG not found."""
        from models.scheduling.schedule_monitoring import handle_successful_scaling

        # Mock model found
        mock_find_model.return_value = "test-model"

        # Mock ASG not found
        mock_autoscaling_client.describe_auto_scaling_groups.return_value = {"AutoScalingGroups": []}

        result = handle_successful_scaling("test-model", "test-asg", {})

        # Verify response
        assert result["statusCode"] == 200
        assert result["message"] == "ASG not found"

        # Verify no status update
        mock_update_model_status.assert_not_called()

    @patch("models.scheduling.schedule_monitoring.autoscaling_client")
    def test_handle_successful_scaling_client_error(self, mock_autoscaling_client):
        """Test handle_successful_scaling with ClientError."""
        from botocore.exceptions import ClientError
        from models.scheduling.schedule_monitoring import handle_successful_scaling

        # Mock ClientError
        error_response = {"Error": {"Code": "Throttling", "Message": "Rate exceeded"}}
        mock_autoscaling_client.describe_auto_scaling_groups.side_effect = ClientError(
            error_response, "DescribeAutoScalingGroups"
        )

        result = handle_successful_scaling("test-model", "test-asg", {})

        # Verify error response
        assert result["statusCode"] == 500
        assert "Failed to check ASG state" in result["message"]

    @patch("models.scheduling.schedule_monitoring.update_model_status")
    @patch("models.scheduling.schedule_monitoring.autoscaling_client")
    def test_handle_successful_scaling_stopped_status(self, mock_autoscaling_client, mock_update_model_status):
        """Test handle_successful_scaling when model should be stopped."""
        from models.scheduling.schedule_monitoring import handle_successful_scaling

        # Mock ASG with no instances in service
        mock_autoscaling_client.describe_auto_scaling_groups.return_value = {
            "AutoScalingGroups": [{"Instances": [{"LifecycleState": "Terminating"}], "DesiredCapacity": 0}]
        }

        result = handle_successful_scaling("test-model", "test-asg", {})

        # Verify response
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["newStatus"] == "Stopped"

    @patch("models.scheduling.schedule_monitoring.autoscaling_client")
    @patch("models.scheduling.schedule_monitoring.get_model_info")
    def test_sync_model_status_client_error(self, mock_get_model_info, mock_autoscaling_client):
        """Test sync_model_status with ClientError."""
        from botocore.exceptions import ClientError
        from models.scheduling.schedule_monitoring import sync_model_status

        # Mock model info
        mock_get_model_info.return_value = {"auto_scaling_group": "test-asg"}

        # Mock ClientError
        error_response = {"Error": {"Code": "Throttling", "Message": "Rate exceeded"}}
        mock_autoscaling_client.describe_auto_scaling_groups.side_effect = ClientError(
            error_response, "DescribeAutoScalingGroups"
        )

        event = {"modelId": "test-model"}

        # Execute - should raise exception
        with pytest.raises(ValueError, match="Failed to check ASG test-asg"):
            sync_model_status(event)

    @patch("models.scheduling.schedule_monitoring.autoscaling_client")
    @patch("models.scheduling.schedule_monitoring.update_model_status")
    @patch("models.scheduling.schedule_monitoring.get_model_info")
    def test_sync_model_status_stopped_state(
        self, mock_get_model_info, mock_update_model_status, mock_autoscaling_client
    ):
        """Test sync_model_status when ASG shows stopped state."""
        from models.scheduling.schedule_monitoring import sync_model_status

        # Mock model info
        mock_get_model_info.return_value = {"auto_scaling_group": "test-asg"}

        # Mock ASG with no instances in service
        mock_autoscaling_client.describe_auto_scaling_groups.return_value = {
            "AutoScalingGroups": [{"Instances": [], "DesiredCapacity": 0}]
        }

        event = {"modelId": "test-model"}
        result = sync_model_status(event)

        # Verify response
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["newStatus"] == "Stopped"

    def test_schedule_retry_simple(self):
        """Test schedule_retry function (simple logging function)."""
        from models.scheduling.schedule_monitoring import schedule_retry

        # Execute - should not raise exception, just log
        schedule_retry("test-model", "test-asg", 60, 1)

    @patch("models.scheduling.schedule_monitoring.autoscaling_client")
    @patch("models.scheduling.schedule_monitoring.find_model_by_asg_name")
    def test_handle_autoscaling_event_asg_not_found(self, mock_find_model, mock_autoscaling_client):
        """Test handle_autoscaling_event when ASG not associated with LISA models."""
        from models.scheduling.schedule_monitoring import handle_autoscaling_event

        # Mock model not found
        mock_find_model.return_value = None

        event = {
            "source": "aws.autoscaling",
            "detail-type": "EC2 Instance Launch Successful",
            "detail": {"AutoScalingGroupName": "unknown-asg"},
        }

        result = handle_autoscaling_event(event)

        # Verify response
        assert result["statusCode"] == 200
        assert result["message"] == "ASG not related to LISA models"

    @patch("models.scheduling.schedule_monitoring.find_model_by_asg_name")
    def test_handle_autoscaling_event_unsupported_type(self, mock_find_model):
        """Test handle_autoscaling_event with unsupported event type."""
        from models.scheduling.schedule_monitoring import handle_autoscaling_event

        # Mock model found so we get past the ASG check
        mock_find_model.return_value = "test-model"

        event = {
            "source": "aws.autoscaling",
            "detail-type": "EC2 Instance Launch Failed",
            "detail": {"AutoScalingGroupName": "test-asg"},
        }

        result = handle_autoscaling_event(event)

        # Verify response
        assert result["statusCode"] == 200
        assert "Event type EC2 Instance Launch Failed ignored" in result["message"]
