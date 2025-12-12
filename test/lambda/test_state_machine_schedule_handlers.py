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

"""Unit tests for state machine schedule handlers."""

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
os.environ["SCHEDULE_MANAGEMENT_FUNCTION_NAME"] = "test-schedule-management-function"


@pytest.fixture
def lambda_context():
    """Mock Lambda context object."""
    context = MagicMock()
    context.function_name = "state-machine-schedule-handlers"
    context.function_version = "1"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:state-machine-schedule-handlers"
    context.memory_limit_in_mb = 128
    context.log_group_name = "/aws/lambda/state-machine-schedule-handlers"
    context.log_stream_name = "2025/01/01/[$LATEST]abcdef123456"
    context.aws_request_id = "00000000-0000-0000-0000-000000000000"
    return context


class TestStateMachineScheduleHandlers:
    """Test state machine schedule handler functions."""

    @patch("models.state_machine.schedule_handlers.schedule_management.update_schedule")
    def test_handle_schedule_creation_success(self, mock_update_schedule, lambda_context):
        """Test successful schedule creation."""
        from models.state_machine.schedule_handlers import handle_schedule_creation

        # Mock event with scheduling config
        event = {
            "modelId": "test-model",
            "autoScalingGroup": "test-asg",
            "autoScalingConfig": {
                "scheduling": {
                    "scheduleType": "RECURRING",
                    "timezone": "UTC",
                    "dailySchedule": {"startTime": "09:00", "stopTime": "17:00"},
                }
            },
        }

        # Mock successful schedule management response
        mock_update_schedule.return_value = {
            "statusCode": 200,
            "body": json.dumps({"message": "Schedule created successfully", "scheduledActionArns": ["arn1", "arn2"]}),
        }

        # Execute
        result = handle_schedule_creation(event, lambda_context)

        # Verify result
        assert result["modelId"] == "test-model"
        assert result["scheduled_action_arns"] == ["arn1", "arn2"]

        # Verify schedule management was called
        mock_update_schedule.assert_called_once()

    def test_handle_schedule_creation_no_scheduling(self, lambda_context):
        """Test schedule creation with no scheduling config."""
        from models.state_machine.schedule_handlers import handle_schedule_creation

        # Mock event without scheduling
        event = {"modelId": "test-model", "autoScalingConfig": {"scheduling": {"scheduleType": "NONE"}}}

        # Execute
        result = handle_schedule_creation(event, lambda_context)

        # Verify result (should pass through unchanged)
        assert result["modelId"] == "test-model"
        assert "scheduled_action_arns" not in result

    def test_handle_schedule_creation_no_asg(self, lambda_context):
        """Test schedule creation without ASG."""
        from models.state_machine.schedule_handlers import handle_schedule_creation

        # Mock event with scheduling but no ASG
        event = {
            "modelId": "test-model",
            "autoScalingConfig": {
                "scheduling": {
                    "scheduleType": "RECURRING",
                    "timezone": "UTC",
                    "dailySchedule": {"startTime": "09:00", "stopTime": "17:00"},
                }
            },
            # Missing autoScalingGroup
        }

        # Execute
        result = handle_schedule_creation(event, lambda_context)

        # Verify result (should pass through unchanged, no schedule management call)
        assert result["modelId"] == "test-model"
        assert "scheduled_action_arns" not in result

    @patch("models.state_machine.schedule_handlers.schedule_management.update_schedule")
    @patch("models.state_machine.schedule_handlers.update_schedule_failure_status")
    def test_handle_schedule_creation_lambda_error(self, mock_update_failure, mock_update_schedule, lambda_context):
        """Test schedule creation with schedule management error."""
        from models.state_machine.schedule_handlers import handle_schedule_creation

        # Mock event with scheduling config
        event = {
            "modelId": "test-model",
            "autoScalingGroup": "test-asg",
            "autoScalingConfig": {
                "scheduling": {
                    "scheduleType": "RECURRING",
                    "timezone": "UTC",
                    "dailySchedule": {"startTime": "09:00", "stopTime": "17:00"},
                }
            },
        }

        # Mock schedule management error response
        mock_update_schedule.side_effect = Exception("Schedule management failed")

        # Execute
        result = handle_schedule_creation(event, lambda_context)

        # Verify result (should pass through, but failure status updated)
        assert result["modelId"] == "test-model"
        mock_update_failure.assert_called_once_with("test-model", "Schedule management failed")

    @patch("models.state_machine.schedule_handlers.schedule_management.update_schedule")
    def test_handle_schedule_update_success(self, mock_update_schedule, lambda_context):
        """Test successful schedule update."""
        from models.state_machine.schedule_handlers import handle_schedule_update

        # Mock event with schedule update
        event = {
            "modelId": "test-model",
            "autoScalingGroup": "test-asg",
            "has_schedule_update": True,
            "autoScalingConfig": {
                "scheduling": {
                    "scheduleType": "RECURRING_DAILY",
                    "timezone": "UTC",
                    "dailySchedule": {"startTime": "10:00", "stopTime": "18:00"},
                }
            },
        }

        # Mock successful schedule management response
        mock_update_schedule.return_value = {
            "statusCode": 200,
            "body": json.dumps({"message": "Schedule updated successfully", "scheduledActionArns": ["arn1", "arn2"]}),
        }

        # Execute
        result = handle_schedule_update(event, lambda_context)

        # Verify result
        assert result["modelId"] == "test-model"
        assert result["scheduled_action_arns"] == ["arn1", "arn2"]

    def test_handle_schedule_update_no_update_needed(self, lambda_context):
        """Test schedule update when no update is needed."""
        from models.state_machine.schedule_handlers import handle_schedule_update

        # Mock event without schedule update flag
        event = {"modelId": "test-model", "has_schedule_update": False}

        # Execute
        result = handle_schedule_update(event, lambda_context)

        # Verify result (should pass through unchanged)
        assert result["modelId"] == "test-model"
        assert "scheduled_action_arns" not in result

    @patch("models.state_machine.schedule_handlers.schedule_management.delete_schedule")
    def test_handle_cleanup_schedule_success(self, mock_delete_schedule, lambda_context):
        """Test successful schedule cleanup."""
        from models.state_machine.schedule_handlers import handle_cleanup_schedule

        # Mock event
        event = {"modelId": "test-model"}

        # Mock successful schedule management response
        mock_delete_schedule.return_value = {
            "statusCode": 200,
            "body": json.dumps({"message": "Schedule deleted successfully"}),
        }

        # Execute
        result = handle_cleanup_schedule(event, lambda_context)

        # Verify result
        assert result["modelId"] == "test-model"

        # Verify schedule management was called
        mock_delete_schedule.assert_called_once()

    @patch("models.state_machine.schedule_handlers.model_table")
    def test_update_schedule_failure_status_success(self, mock_model_table):
        """Test successful schedule failure status update."""
        from models.state_machine.schedule_handlers import update_schedule_failure_status

        mock_model_table.update_item.return_value = {}

        # Execute
        update_schedule_failure_status("test-model", "Test error message")

        # Verify update_item was called
        mock_model_table.update_item.assert_called_once()
        call_args = mock_model_table.update_item.call_args
        assert call_args[1]["Key"] == {"model_id": "test-model"}
        assert call_args[1]["ExpressionAttributeValues"][":failed"] is True


class TestScheduleCreationEdgeCases:
    """Test edge cases for schedule creation."""

    @patch("models.state_machine.schedule_handlers.schedule_management.update_schedule")
    @patch("models.state_machine.schedule_handlers.update_schedule_failure_status")
    def test_handle_schedule_creation_lambda_error(self, mock_update_failure, mock_update_schedule, lambda_context):
        """Test schedule creation with schedule management error."""
        from models.state_machine.schedule_handlers import handle_schedule_creation

        # Mock event with scheduling config
        event = {
            "modelId": "test-model",
            "autoScalingGroup": "test-asg",
            "autoScalingConfig": {
                "scheduling": {
                    "scheduleType": "RECURRING",
                    "timezone": "UTC",
                    "dailySchedule": {"startTime": "09:00", "stopTime": "17:00"},
                }
            },
        }

        # Mock schedule management exception
        mock_update_schedule.side_effect = Exception("Schedule management failed")

        # Execute
        result = handle_schedule_creation(event, lambda_context)

        # Verify result (should pass through, but failure status updated)
        assert result["modelId"] == "test-model"
        mock_update_failure.assert_called_once_with("test-model", "Schedule management failed")

    @patch("models.state_machine.schedule_handlers.schedule_management.update_schedule")
    @patch("models.state_machine.schedule_handlers.update_schedule_failure_status")
    def test_handle_schedule_update_exception(self, mock_update_failure, mock_update_schedule, lambda_context):
        """Test schedule update with exception."""
        from models.state_machine.schedule_handlers import handle_schedule_update

        # Mock event with schedule update
        event = {
            "modelId": "test-model",
            "autoScalingGroup": "test-asg",
            "has_schedule_update": True,
            "autoScalingConfig": {
                "scheduling": {
                    "scheduleType": "RECURRING_DAILY",
                    "timezone": "UTC",
                    "dailySchedule": {"startTime": "10:00", "stopTime": "18:00"},
                }
            },
        }

        # Mock schedule management exception
        mock_update_schedule.side_effect = Exception("Schedule management failed")

        # Execute
        result = handle_schedule_update(event, lambda_context)

        # Verify result (should pass through, but failure status updated)
        assert result["modelId"] == "test-model"
        mock_update_failure.assert_called_once_with("test-model", "Schedule management failed")

    @patch("models.state_machine.schedule_handlers.schedule_management.delete_schedule")
    def test_handle_cleanup_schedule_exception(self, mock_delete_schedule, lambda_context):
        """Test schedule cleanup with exception."""
        from models.state_machine.schedule_handlers import handle_cleanup_schedule

        # Mock event
        event = {"modelId": "test-model"}

        # Mock schedule management exception
        mock_delete_schedule.side_effect = Exception("Schedule management failed")

        # Execute (should not raise exception)
        result = handle_cleanup_schedule(event, lambda_context)

        # Verify result (should pass through even with exception)
        assert result["modelId"] == "test-model"

    @patch("models.state_machine.schedule_handlers.model_table")
    def test_update_schedule_failure_status_exception(self, mock_model_table):
        """Test schedule failure status update with exception."""
        from models.state_machine.schedule_handlers import update_schedule_failure_status

        # Mock DynamoDB exception
        mock_model_table.update_item.side_effect = Exception("DynamoDB error")

        # Execute (should not raise exception)
        update_schedule_failure_status("test-model", "Test error message")

        # Verify update_item was called (exception should be caught)
        mock_model_table.update_item.assert_called_once()
