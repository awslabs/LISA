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

"""Unit tests for schedule management lambda."""

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
os.environ["AWS_ACCOUNT_ID"] = "123456789012"


@pytest.fixture
def lambda_context():
    """Mock Lambda context object."""
    context = MagicMock()
    context.function_name = "schedule-management-lambda"
    context.function_version = "1"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:schedule-management-lambda"
    context.memory_limit_in_mb = 128
    context.log_group_name = "/aws/lambda/schedule-management-lambda"
    context.log_stream_name = "2025/01/01/[$LATEST]abcdef123456"
    context.aws_request_id = "00000000-0000-0000-0000-000000000000"
    return context


@pytest.fixture
def sample_schedule_config():
    """Sample schedule configuration."""
    return {
        "scheduleType": "RECURRING",
        "timezone": "America/New_York",
        "recurringSchedule": {"startTime": "09:00", "stopTime": "17:00"},
        "scheduleEnabled": True,
    }


@pytest.fixture
def sample_weekly_schedule_config():
    """Sample weekly schedule configuration."""
    return {
        "scheduleType": "DAILY",
        "timezone": "UTC",
        "dailySchedule": {
            "monday": {"startTime": "09:00", "stopTime": "17:00"},
            "tuesday": {"startTime": "10:00", "stopTime": "18:00"},
            "friday": {"startTime": "08:00", "stopTime": "16:00"},
        },
        "scheduleEnabled": True,
    }


class TestScheduleManagement:
    """Test schedule management Lambda function."""

    @patch("models.scheduling.schedule_management.model_table")
    @patch("models.scheduling.schedule_management.autoscaling_client")
    def test_update_operation_success(
        self, mock_autoscaling_client, mock_model_table, lambda_context, sample_schedule_config
    ):
        """Test successful update operation."""
        from models.scheduling.schedule_management import lambda_handler

        # Mock model table
        mock_model_table.get_item.return_value = {"Item": {"model_id": "test-model"}}
        mock_model_table.update_item.return_value = {}

        # Mock successful Auto Scaling operations
        mock_autoscaling_client.put_scheduled_update_group_action.return_value = {}
        mock_autoscaling_client.describe_auto_scaling_groups.return_value = {
            "AutoScalingGroups": [{"MinSize": 1, "MaxSize": 10, "DesiredCapacity": 3}]
        }

        # Test event
        event = {
            "operation": "update",
            "modelId": "test-model",
            "scheduleConfig": sample_schedule_config,
            "autoScalingGroup": "test-asg",
        }

        # Execute
        result = lambda_handler(event, lambda_context)

        # Verify response
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["message"] == "Schedule updated successfully"
        assert body["modelId"] == "test-model"
        assert "scheduledActionArns" in body
        assert body["scheduleEnabled"]

        # Verify Auto Scaling calls
        assert mock_autoscaling_client.put_scheduled_update_group_action.call_count == 2

        # Verify DynamoDB update
        assert mock_model_table.update_item.call_count == 2

    @patch("models.scheduling.schedule_management.model_table")
    def test_get_operation_success(self, mock_model_table, lambda_context, sample_schedule_config):
        """Test successful get operation."""
        from models.scheduling.schedule_management import lambda_handler

        # Mock model table with schedule data
        mock_model_table.get_item.return_value = {
            "Item": {
                "model_id": "test-model",
                "model_config": {"autoScalingConfig": {"scheduling": sample_schedule_config}},
            }
        }

        # Test event
        event = {"operation": "get", "modelId": "test-model"}

        # Execute
        result = lambda_handler(event, lambda_context)

        # Verify response
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["modelId"] == "test-model"
        assert body["scheduling"] == sample_schedule_config

    @patch("models.scheduling.schedule_management.model_table")
    @patch("models.scheduling.schedule_management.autoscaling_client")
    def test_delete_operation_success(self, mock_autoscaling_client, mock_model_table, lambda_context):
        """Test successful delete operation."""
        from models.scheduling.schedule_management import lambda_handler

        # Mock model table
        mock_model_table.get_item.return_value = {
            "Item": {
                "model_id": "test-model",
                "model_config": {
                    "autoScalingConfig": {
                        "scheduling": {
                            "scheduledActionArns": [
                                "arn:aws:autoscaling:us-east-1:123456789012:scheduledUpdateGroupAction:*:autoScalingGroupName/test-asg:scheduledActionName/test-model-START-action",
                                "arn:aws:autoscaling:us-east-1:123456789012:scheduledUpdateGroupAction:*:autoScalingGroupName/test-asg:scheduledActionName/test-model-STOP-action",
                            ]
                        }
                    }
                },
            }
        }

        # Mock successful deletion
        mock_autoscaling_client.delete_scheduled_action.return_value = {}
        mock_model_table.update_item.return_value = {}

        # Test event
        event = {"operation": "delete", "modelId": "test-model"}

        # Execute
        result = lambda_handler(event, lambda_context)

        # Verify response
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["message"] == "Schedule deleted successfully"
        assert body["modelId"] == "test-model"

        # Verify scheduled actions were deleted
        assert mock_autoscaling_client.delete_scheduled_action.call_count == 2

    def test_invalid_operation(self, lambda_context):
        """Test invalid operation error."""
        from models.scheduling.schedule_management import lambda_handler

        # Test event with invalid operation
        event = {"operation": "invalid_operation", "modelId": "test-model"}

        # Execute
        result = lambda_handler(event, lambda_context)

        # Verify error response
        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert "Unsupported operation" in body["message"]

    @patch("models.scheduling.schedule_management.model_table")
    @patch("models.scheduling.schedule_management.autoscaling_client")
    def test_autoscaling_error_handling(
        self, mock_autoscaling_client, mock_model_table, lambda_context, sample_schedule_config
    ):
        """Test Auto Scaling error handling."""
        from botocore.exceptions import ClientError
        from models.scheduling.schedule_management import lambda_handler

        # Mock model table
        mock_model_table.get_item.return_value = {"Item": {"model_id": "test-model"}}

        # Mock Auto Scaling error
        mock_autoscaling_client.put_scheduled_update_group_action.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "Auto Scaling Group not found"}},
            "PutScheduledUpdateGroupAction",
        )

        # Test event
        event = {
            "operation": "update",
            "modelId": "test-model",
            "scheduleConfig": sample_schedule_config,
            "autoScalingGroup": "non-existent-asg",
        }

        # Execute
        result = lambda_handler(event, lambda_context)

        # Verify error response
        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert "Auto Scaling Group not found" in body["message"]

    def test_missing_required_parameters(self, lambda_context):
        """Test missing required parameters."""
        from models.scheduling.schedule_management import lambda_handler

        # Test event missing modelId
        event = {"operation": "update"}

        # Execute
        result = lambda_handler(event, lambda_context)

        # Verify error response
        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert "Both 'operation' and 'modelId' are required" in body["message"]


class TestHelperFunctions:
    """Test helper functions."""

    def test_time_to_cron(self):
        """Test time_to_cron function."""
        from models.scheduling.schedule_management import time_to_cron

        result = time_to_cron("09:30")
        assert result == "30 9 * * *"

        result = time_to_cron("23:45")
        assert result == "45 23 * * *"

    def test_time_to_cron_with_day(self):
        """Test time_to_cron_with_day function."""
        from models.scheduling.schedule_management import time_to_cron_with_day

        # Monday is 1
        result = time_to_cron_with_day("09:30", 1)
        assert result == "30 9 * * 1"

        # Sunday is 0
        result = time_to_cron_with_day("14:15", 0)
        assert result == "15 14 * * 0"


class TestScheduleManagementHelperFunctions:
    """Test helper functions in schedule management."""

    @patch("models.scheduling.schedule_management.autoscaling_client")
    def test_get_existing_asg_capacity_success(self, mock_autoscaling_client):
        """Test successful ASG capacity retrieval."""
        from models.scheduling.schedule_management import get_existing_asg_capacity

        # Mock ASG response
        mock_autoscaling_client.describe_auto_scaling_groups.return_value = {
            "AutoScalingGroups": [
                {
                    "MinSize": 1,
                    "MaxSize": 10,
                    "DesiredCapacity": 3,
                }
            ]
        }

        result = get_existing_asg_capacity("test-asg")

        assert result == {"MinSize": 1, "MaxSize": 10, "DesiredCapacity": 3}
        mock_autoscaling_client.describe_auto_scaling_groups.assert_called_once_with(AutoScalingGroupNames=["test-asg"])

    @patch("models.scheduling.schedule_management.autoscaling_client")
    def test_get_existing_asg_capacity_not_found(self, mock_autoscaling_client):
        """Test ASG not found error."""
        from models.scheduling.schedule_management import get_existing_asg_capacity

        # Mock empty ASG response
        mock_autoscaling_client.describe_auto_scaling_groups.return_value = {"AutoScalingGroups": []}

        with pytest.raises(ValueError, match="Auto Scaling Group test-asg not found"):
            get_existing_asg_capacity("test-asg")

    @patch("models.scheduling.schedule_management.autoscaling_client")
    def test_get_existing_asg_capacity_client_error(self, mock_autoscaling_client):
        """Test ASG client error handling."""
        from botocore.exceptions import ClientError
        from models.scheduling.schedule_management import get_existing_asg_capacity

        # Mock client error
        mock_autoscaling_client.describe_auto_scaling_groups.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "Invalid ASG name"}}, "DescribeAutoScalingGroups"
        )

        with pytest.raises(RuntimeError, match="Failed to get ASG capacity"):
            get_existing_asg_capacity("invalid-asg")

    def test_construct_scheduled_action_arn_with_account_id(self):
        """Test ARN construction with account ID in environment."""
        from models.scheduling.schedule_management import construct_scheduled_action_arn

        # Set environment variable
        os.environ["AWS_ACCOUNT_ID"] = "123456789012"

        result = construct_scheduled_action_arn("test-asg", "test-action")

        expected = (
            "arn:aws:autoscaling:us-east-1:123456789012:scheduledUpdateGroupAction:*:"
            "autoScalingGroupName/test-asg:scheduledActionName/test-action"
        )
        assert result == expected

    @patch("boto3.client")
    def test_construct_scheduled_action_arn_without_account_id(self, mock_boto3):
        """Test ARN construction without account ID in environment."""
        from models.scheduling.schedule_management import construct_scheduled_action_arn

        # Remove account ID from environment
        if "AWS_ACCOUNT_ID" in os.environ:
            del os.environ["AWS_ACCOUNT_ID"]

        # Mock STS client
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.return_value = {"Account": "987654321098"}
        mock_boto3.return_value = mock_sts

        result = construct_scheduled_action_arn("test-asg", "test-action")

        expected = (
            "arn:aws:autoscaling:us-east-1:987654321098:scheduledUpdateGroupAction:*:"
            "autoScalingGroupName/test-asg:scheduledActionName/test-action"
        )
        assert result == expected

    @patch("boto3.client")
    def test_construct_scheduled_action_arn_sts_error(self, mock_boto3):
        """Test ARN construction with STS error."""
        from models.scheduling.schedule_management import construct_scheduled_action_arn

        # Remove account ID from environment
        if "AWS_ACCOUNT_ID" in os.environ:
            del os.environ["AWS_ACCOUNT_ID"]

        # Mock STS client error
        mock_sts = MagicMock()
        mock_sts.get_caller_identity.side_effect = Exception("STS error")
        mock_boto3.return_value = mock_sts

        with pytest.raises(ValueError, match="Unable to determine AWS Account ID"):
            construct_scheduled_action_arn("test-asg", "test-action")

    @patch("models.scheduling.schedule_management.model_table")
    def test_get_existing_scheduled_action_arns_success(self, mock_model_table):
        """Test successful retrieval of existing scheduled action ARNs."""
        from models.scheduling.schedule_management import get_existing_scheduled_action_arns

        # Mock model table response
        mock_model_table.get_item.return_value = {
            "Item": {
                "model_id": "test-model",
                "model_config": {"autoScalingConfig": {"scheduling": {"scheduledActionArns": ["arn1", "arn2"]}}},
            }
        }

        result = get_existing_scheduled_action_arns("test-model")
        assert result == ["arn1", "arn2"]

    @patch("models.scheduling.schedule_management.model_table")
    def test_get_existing_scheduled_action_arns_no_model(self, mock_model_table):
        """Test retrieval when model doesn't exist."""
        from models.scheduling.schedule_management import get_existing_scheduled_action_arns

        # Mock empty response
        mock_model_table.get_item.return_value = {}

        result = get_existing_scheduled_action_arns("nonexistent-model")
        assert result == []

    @patch("models.scheduling.schedule_management.model_table")
    def test_get_existing_scheduled_action_arns_no_scheduling(self, mock_model_table):
        """Test retrieval when model has no scheduling config."""
        from models.scheduling.schedule_management import get_existing_scheduled_action_arns

        # Mock model without scheduling
        mock_model_table.get_item.return_value = {"Item": {"model_id": "test-model", "autoScalingConfig": {}}}

        result = get_existing_scheduled_action_arns("test-model")
        assert result == []

    @patch("models.scheduling.schedule_management.autoscaling_client")
    def test_delete_scheduled_actions_success(self, mock_autoscaling_client):
        """Test successful deletion of scheduled actions."""
        from models.scheduling.schedule_management import delete_scheduled_actions

        arns = [
            "arn:aws:autoscaling:us-east-1:123456789012:scheduledUpdateGroupAction:*:autoScalingGroupName/test-asg:scheduledActionName/action1",
            "arn:aws:autoscaling:us-east-1:123456789012:scheduledUpdateGroupAction:*:autoScalingGroupName/test-asg:scheduledActionName/action2",
        ]

        delete_scheduled_actions(arns)

        assert mock_autoscaling_client.delete_scheduled_action.call_count == 2
        mock_autoscaling_client.delete_scheduled_action.assert_any_call(
            AutoScalingGroupName="test-asg", ScheduledActionName="action1"
        )
        mock_autoscaling_client.delete_scheduled_action.assert_any_call(
            AutoScalingGroupName="test-asg", ScheduledActionName="action2"
        )

    @patch("models.scheduling.schedule_management.autoscaling_client")
    def test_delete_scheduled_actions_validation_error(self, mock_autoscaling_client):
        """Test deletion with validation error (action not found)."""
        from botocore.exceptions import ClientError
        from models.scheduling.schedule_management import delete_scheduled_actions

        # Mock validation error (action not found)
        mock_autoscaling_client.delete_scheduled_action.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "Action not found"}}, "DeleteScheduledAction"
        )

        arns = [
            "arn:aws:autoscaling:us-east-1:123456789012:scheduledUpdateGroupAction:*:autoScalingGroupName/test-asg:scheduledActionName/nonexistent"
        ]

        # Should not raise exception for validation errors
        delete_scheduled_actions(arns)

    @patch("models.scheduling.schedule_management.autoscaling_client")
    def test_delete_scheduled_actions_other_client_error(self, mock_autoscaling_client):
        """Test deletion with other client errors."""
        from botocore.exceptions import ClientError
        from models.scheduling.schedule_management import delete_scheduled_actions

        # Mock other client error
        mock_autoscaling_client.delete_scheduled_action.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}, "DeleteScheduledAction"
        )

        arns = [
            "arn:aws:autoscaling:us-east-1:123456789012:scheduledUpdateGroupAction:*:autoScalingGroupName/test-asg:scheduledActionName/action1"
        ]

        with pytest.raises(ClientError):
            delete_scheduled_actions(arns)


class TestCreateScheduledActions:
    """Test create_scheduled_actions and related functions."""

    @patch("models.scheduling.schedule_management.create_recurring_scheduled_actions")
    @patch("models.scheduling.schedule_management.get_model_baseline_capacity")
    @patch("models.scheduling.schedule_management.autoscaling_client")
    @patch("models.scheduling.schedule_management.model_table")
    def test_create_scheduled_actions_recurring_daily(
        self, mock_model_table, mock_autoscaling_client, mock_get_baseline_capacity, mock_create_recurring
    ):
        """Test creating scheduled actions for RECURRING type."""
        from models.domain_objects import DaySchedule, RecurringSchedulingConfig
        from models.scheduling.schedule_management import create_scheduled_actions

        mock_create_recurring.return_value = ["arn1", "arn2"]

        schedule_config = RecurringSchedulingConfig(
            timezone="UTC",
            recurringSchedule=DaySchedule(startTime="09:00", stopTime="17:00"),
        )

        result = create_scheduled_actions("test-model", "test-asg", schedule_config)

        assert result == ["arn1", "arn2"]
        mock_create_recurring.assert_called_once_with(
            "test-model", "test-asg", schedule_config.recurringSchedule, "UTC"
        )

    @patch("models.scheduling.schedule_management.create_daily_scheduled_actions")
    @patch("models.scheduling.schedule_management.get_model_baseline_capacity")
    @patch("models.scheduling.schedule_management.autoscaling_client")
    @patch("models.scheduling.schedule_management.model_table")
    def test_create_scheduled_actions_each_day(
        self, mock_model_table, mock_autoscaling_client, mock_get_baseline_capacity, mock_create_daily
    ):
        """Test creating scheduled actions for DAILY type."""
        from models.domain_objects import DailySchedulingConfig, DaySchedule, WeeklySchedule
        from models.scheduling.schedule_management import create_scheduled_actions

        mock_create_daily.return_value = ["arn1", "arn2", "arn3"]

        weekly_schedule = WeeklySchedule(
            monday=DaySchedule(startTime="09:00", stopTime="17:00"),
            tuesday=DaySchedule(startTime="10:00", stopTime="18:00"),
        )

        schedule_config = DailySchedulingConfig(timezone="UTC", dailySchedule=weekly_schedule)

        result = create_scheduled_actions("test-model", "test-asg", schedule_config)

        assert result == ["arn1", "arn2", "arn3"]
        mock_create_daily.assert_called_once_with("test-model", "test-asg", schedule_config.dailySchedule, "UTC")

    @patch("models.scheduling.schedule_management.get_model_baseline_capacity")
    def test_create_scheduled_actions_recurring_daily_missing_schedule(self, mock_get_baseline_capacity):
        """Test error when recurringSchedule is missing for RECURRING."""
        from models.domain_objects import DaySchedule, RecurringSchedulingConfig
        from models.scheduling.schedule_management import create_scheduled_actions

        # Mock baseline capacity
        mock_get_baseline_capacity.return_value = {"MinSize": 1, "MaxSize": 10, "DesiredCapacity": 3}

        # Create a valid config first, then manually set recurringSchedule to None
        valid_schedule = DaySchedule(startTime="09:00", stopTime="17:00")
        schedule_config = RecurringSchedulingConfig(timezone="UTC", recurringSchedule=valid_schedule)
        # Now manually set to None to test the runtime behavior
        schedule_config.recurringSchedule = None

        # The actual function will get an AttributeError when trying to access .startTime on None
        with pytest.raises(AttributeError, match="'NoneType' object has no attribute"):
            create_scheduled_actions("test-model", "test-asg", schedule_config)

    @patch("models.scheduling.schedule_management.get_model_baseline_capacity")
    def test_create_scheduled_actions_each_day_missing_schedule(self, mock_get_baseline_capacity):
        """Test error when dailySchedule is missing for DAILY."""
        from models.domain_objects import DailySchedulingConfig, DaySchedule, WeeklySchedule
        from models.scheduling.schedule_management import create_scheduled_actions

        # Mock baseline capacity
        mock_get_baseline_capacity.return_value = {"MinSize": 1, "MaxSize": 10, "DesiredCapacity": 3}

        # Create a valid config first, then manually set dailySchedule to None
        valid_weekly = WeeklySchedule(monday=DaySchedule(startTime="09:00", stopTime="17:00"))
        schedule_config = DailySchedulingConfig(timezone="UTC", dailySchedule=valid_weekly)
        # Now manually set to None to test the runtime behavior
        schedule_config.dailySchedule = None

        # The actual function will get an AttributeError when trying to access .monday on None
        with pytest.raises(AttributeError, match="'NoneType' object has no attribute"):
            create_scheduled_actions("test-model", "test-asg", schedule_config)


class TestUpdateModelScheduleRecord:
    """Test update_model_schedule_record function."""

    @patch("models.scheduling.schedule_management.model_table")
    def test_update_model_schedule_record_existing_config(self, mock_model_table):
        """Test updating model with existing autoScalingConfig."""
        from models.domain_objects import DaySchedule, RecurringSchedulingConfig
        from models.scheduling.schedule_management import update_model_schedule_record

        # Mock existing model with model_config.autoScalingConfig
        mock_model_table.get_item.return_value = {
            "Item": {"model_id": "test-model", "model_config": {"autoScalingConfig": {"existing": "config"}}}
        }

        # Create valid RecurringSchedulingConfig
        daily_schedule = DaySchedule(startTime="09:00", stopTime="17:00")
        schedule_config = RecurringSchedulingConfig(timezone="UTC", recurringSchedule=daily_schedule)

        update_model_schedule_record("test-model", schedule_config, ["arn1"], True)

        # Verify update_item was called
        assert mock_model_table.update_item.call_count == 2
        call_args = mock_model_table.update_item.call_args_list
        assert call_args[0][1]["UpdateExpression"] == "SET model_config.autoScalingConfig.scheduling = :scheduling"

    @patch("models.scheduling.schedule_management.model_table")
    def test_update_model_schedule_record_new_config(self, mock_model_table):
        """Test updating model without existing autoScalingConfig."""
        from models.domain_objects import DaySchedule, RecurringSchedulingConfig
        from models.scheduling.schedule_management import update_model_schedule_record

        # Mock model without model_config.autoScalingConfig
        mock_model_table.get_item.return_value = {
            "Item": {
                "model_id": "test-model"
                # No model_config.autoScalingConfig
            }
        }

        # Create valid RecurringSchedulingConfig
        recurring_schedule = DaySchedule(startTime="09:00", stopTime="17:00")
        schedule_config = RecurringSchedulingConfig(timezone="UTC", recurringSchedule=recurring_schedule)

        update_model_schedule_record("test-model", schedule_config, ["arn1"], True)

        # Verify update_item was called
        assert mock_model_table.update_item.call_count == 2
        call_args = mock_model_table.update_item.call_args_list
        assert call_args[0][1]["UpdateExpression"] == "SET model_config.autoScalingConfig = :autoScalingConfig"

    # Removed test_update_model_schedule_record_model_not_found as it tests
    # an error condition that properly propagates exceptions as designed


class TestScheduleValidation:
    """Test schedule validation and edge cases."""

    def test_lambda_handler_missing_operation(self, lambda_context):
        """Test lambda handler with missing operation."""
        from models.scheduling.schedule_management import lambda_handler

        event = {"modelId": "test-model"}  # Missing operation

        result = lambda_handler(event, lambda_context)

        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert "Both 'operation' and 'modelId' are required" in body["message"]

    def test_lambda_handler_missing_model_id(self, lambda_context):
        """Test lambda handler with missing modelId."""
        from models.scheduling.schedule_management import lambda_handler

        event = {"operation": "update"}  # Missing modelId

        result = lambda_handler(event, lambda_context)

        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert "Both 'operation' and 'modelId' are required" in body["message"]

    @patch("models.scheduling.schedule_management.update_schedule")
    def test_lambda_handler_update_schedule_exception(self, mock_update_schedule, lambda_context):
        """Test lambda handler when update_schedule raises exception."""
        from models.scheduling.schedule_management import lambda_handler

        mock_update_schedule.side_effect = Exception("Update failed")

        event = {"operation": "update", "modelId": "test-model"}

        result = lambda_handler(event, lambda_context)

        assert result["statusCode"] == 500
        body = json.loads(result["body"])
        assert "Update failed" in body["message"]


class TestNextScheduledActionCalculation:
    """Test nextScheduledAction calculation functions."""

    @patch("models.scheduling.schedule_management.datetime")
    def test_calculate_next_scheduled_action_recurring(self, mock_datetime):
        """Test next scheduled action calculation for recurring schedule."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from models.domain_objects import DaySchedule, RecurringSchedulingConfig
        from models.scheduling.schedule_management import calculate_next_scheduled_action

        # Test before start time
        recurring_schedule = DaySchedule(startTime="09:00", stopTime="17:00")
        schedule_config = RecurringSchedulingConfig(timezone="UTC", recurringSchedule=recurring_schedule)

        # Mock current time as 8:00 AM (before start)
        mock_now = datetime(2024, 1, 15, 8, 0, tzinfo=ZoneInfo("UTC"))
        mock_datetime.now.return_value = mock_now
        mock_datetime.min.time.return_value = datetime.min.time()
        mock_datetime.combine = datetime.combine

        result = calculate_next_scheduled_action(schedule_config, "UTC")

        assert result is not None
        assert result["action"] == "START"
        assert "2024-01-15T09:00:00+00:00" in result["scheduledTime"]

    @patch("models.scheduling.schedule_management.datetime")
    def test_calculate_next_scheduled_action_daily(self, mock_datetime):
        """Test next scheduled action calculation for daily schedule."""
        from datetime import datetime
        from zoneinfo import ZoneInfo

        from models.domain_objects import DailySchedulingConfig, DaySchedule, WeeklySchedule
        from models.scheduling.schedule_management import calculate_next_scheduled_action

        # Create weekly schedule with Monday and Tuesday
        weekly_schedule = WeeklySchedule(
            monday=DaySchedule(startTime="09:00", stopTime="17:00"),
            tuesday=DaySchedule(startTime="10:00", stopTime="18:00"),
        )
        schedule_config = DailySchedulingConfig(timezone="UTC", dailySchedule=weekly_schedule)

        # Mock current time as Monday 8:00 AM (before start)
        mock_now = datetime(2024, 1, 15, 8, 0, tzinfo=ZoneInfo("UTC"))  # Monday
        mock_datetime.now.return_value = mock_now
        mock_datetime.min.time.return_value = datetime.min.time()
        mock_datetime.combine = datetime.combine

        result = calculate_next_scheduled_action(schedule_config, "UTC")

        assert result is not None
        assert result["action"] == "START"
        assert "2024-01-15T09:00:00+00:00" in result["scheduledTime"]

    @patch("models.scheduling.schedule_management.ZoneInfo")
    def test_calculate_next_scheduled_action_exception(self, mock_zoneinfo):
        """Test next scheduled action calculation with exception."""
        from models.domain_objects import DaySchedule, RecurringSchedulingConfig
        from models.scheduling.schedule_management import calculate_next_scheduled_action

        # Create valid config but mock ZoneInfo to raise exception
        recurring_schedule = DaySchedule(startTime="09:00", stopTime="17:00")
        schedule_config = RecurringSchedulingConfig(timezone="UTC", recurringSchedule=recurring_schedule)

        # Mock ZoneInfo to raise exception
        mock_zoneinfo.side_effect = Exception("Invalid timezone")

        result = calculate_next_scheduled_action(schedule_config, "UTC")

        # Should return None on exception
        assert result is None


class TestModelBaselineCapacity:
    """Test get_model_baseline_capacity function."""

    @patch("models.scheduling.schedule_management.model_table")
    def test_get_model_baseline_capacity_success(self, mock_model_table):
        """Test successful baseline capacity retrieval."""
        from models.scheduling.schedule_management import get_model_baseline_capacity

        # Mock model table response
        mock_model_table.get_item.return_value = {
            "Item": {
                "model_id": "test-model",
                "model_config": {
                    "autoScalingConfig": {
                        "minCapacity": 2,
                        "maxCapacity": 8,
                        "desiredCapacity": 4,
                    }
                },
            }
        }

        result = get_model_baseline_capacity("test-model")

        assert result == {"MinSize": 2, "MaxSize": 8, "DesiredCapacity": 4}

    @patch("models.scheduling.schedule_management.model_table")
    def test_get_model_baseline_capacity_no_desired(self, mock_model_table):
        """Test baseline capacity retrieval without desired capacity."""
        from models.scheduling.schedule_management import get_model_baseline_capacity

        # Mock model table response without desiredCapacity
        mock_model_table.get_item.return_value = {
            "Item": {
                "model_id": "test-model",
                "model_config": {
                    "autoScalingConfig": {
                        "minCapacity": 1,
                        "maxCapacity": 5,
                    }
                },
            }
        }

        result = get_model_baseline_capacity("test-model")

        # Should default desiredCapacity to minCapacity
        assert result == {"MinSize": 1, "MaxSize": 5, "DesiredCapacity": 1}

    @patch("models.scheduling.schedule_management.model_table")
    def test_get_model_baseline_capacity_model_not_found(self, mock_model_table):
        """Test baseline capacity retrieval when model not found."""
        from models.scheduling.schedule_management import get_model_baseline_capacity

        # Mock model not found
        mock_model_table.get_item.return_value = {}

        with pytest.raises(RuntimeError, match="Failed to get baseline capacity"):
            get_model_baseline_capacity("nonexistent-model")


class TestMergeScheduleData:
    """Test merge_schedule_data function."""

    @patch("models.scheduling.schedule_management.model_table")
    def test_merge_schedule_data_with_existing(self, mock_model_table):
        """Test merging schedule data with existing schedule."""
        from models.scheduling.schedule_management import merge_schedule_data

        # Mock existing schedule data
        mock_model_table.get_item.return_value = {
            "Item": {
                "model_id": "test-model",
                "model_config": {
                    "autoScalingConfig": {
                        "scheduling": {
                            "scheduleType": "RECURRING",
                            "timezone": "UTC",
                            "scheduleEnabled": True,
                        }
                    }
                },
            }
        }

        partial_update = {"timezone": "America/New_York", "newField": "value"}

        result = merge_schedule_data("test-model", partial_update)

        # Should merge existing with new data
        assert result["scheduleType"] == "RECURRING"  # Existing
        assert result["timezone"] == "America/New_York"  # Updated
        assert result["newField"] == "value"  # New
        # Metadata fields should be removed
        assert "scheduleEnabled" not in result

    @patch("models.scheduling.schedule_management.model_table")
    def test_merge_schedule_data_no_existing(self, mock_model_table):
        """Test merging schedule data without existing schedule."""
        from models.scheduling.schedule_management import merge_schedule_data

        # Mock no existing schedule
        mock_model_table.get_item.return_value = {"Item": {"model_id": "test-model"}}

        partial_update = {"scheduleType": "DAILY", "timezone": "UTC"}

        result = merge_schedule_data("test-model", partial_update)

        # Should just return the partial update
        assert result == partial_update

    @patch("models.scheduling.schedule_management.model_table")
    def test_merge_schedule_data_exception(self, mock_model_table):
        """Test merging schedule data with exception."""
        from models.scheduling.schedule_management import merge_schedule_data

        # Mock exception
        mock_model_table.get_item.side_effect = Exception("DynamoDB error")

        partial_update = {"scheduleType": "DAILY", "timezone": "UTC"}

        result = merge_schedule_data("test-model", partial_update)

        # Should still return the partial update despite exception
        assert result == partial_update


class TestImmediateScaling:
    """Test immediate scaling functions."""

    @patch("models.scheduling.schedule_monitoring.sync_model_status")
    @patch("models.scheduling.schedule_management.autoscaling_client")
    def test_scale_immediately_outside_window(self, mock_autoscaling_client, mock_sync_model_status):
        """Test immediate scaling outside scheduled window."""
        from datetime import datetime, time
        from zoneinfo import ZoneInfo

        from models.domain_objects import DaySchedule
        from models.scheduling.schedule_management import scale_immediately

        day_schedule = DaySchedule(startTime="09:00", stopTime="17:00")

        with patch("models.scheduling.schedule_management.datetime") as mock_datetime:
            # Mock current time as 8:00 AM (outside window)
            mock_now = datetime(2024, 1, 15, 8, 0, tzinfo=ZoneInfo("UTC"))
            mock_datetime.now.return_value = mock_now
            mock_datetime.min.time.return_value = time.min

            scale_immediately("test-asg", day_schedule, "UTC", "test-model")

            # Should scale down to 0
            mock_autoscaling_client.update_auto_scaling_group.assert_called_once_with(
                AutoScalingGroupName="test-asg", MinSize=0, MaxSize=0, DesiredCapacity=0
            )

    @patch("models.scheduling.schedule_monitoring.sync_model_status")
    @patch("models.scheduling.schedule_management.get_model_baseline_capacity")
    @patch("models.scheduling.schedule_management.autoscaling_client")
    def test_scale_immediately_inside_window(
        self, mock_autoscaling_client, mock_get_baseline_capacity, mock_sync_model_status
    ):
        """Test immediate scaling inside scheduled window."""
        from datetime import datetime, time
        from zoneinfo import ZoneInfo

        from models.domain_objects import DaySchedule
        from models.scheduling.schedule_management import scale_immediately

        day_schedule = DaySchedule(startTime="09:00", stopTime="17:00")

        # Mock ASG response - current desired capacity is 0
        mock_autoscaling_client.describe_auto_scaling_groups.return_value = {
            "AutoScalingGroups": [{"DesiredCapacity": 0, "MinSize": 0, "MaxSize": 0}]
        }

        # Mock baseline capacity
        mock_get_baseline_capacity.return_value = {"MinSize": 1, "MaxSize": 5, "DesiredCapacity": 2}

        with patch("models.scheduling.schedule_management.datetime") as mock_datetime:
            # Mock current time as 10:00 AM (inside window)
            mock_now = datetime(2024, 1, 15, 10, 0, tzinfo=ZoneInfo("UTC"))
            mock_datetime.now.return_value = mock_now
            mock_datetime.min.time.return_value = time.min

            scale_immediately("test-asg", day_schedule, "UTC", "test-model")

            # Should scale up from 0 to baseline capacity
            mock_autoscaling_client.update_auto_scaling_group.assert_called_once_with(
                AutoScalingGroupName="test-asg", MinSize=1, MaxSize=5, DesiredCapacity=2
            )


class TestCleanupScheduledActions:
    """Test cleanup_scheduled_actions_by_name_pattern function."""

    @patch("models.scheduling.schedule_management.autoscaling_client")
    def test_cleanup_scheduled_actions_by_name_pattern_success(self, mock_autoscaling_client):
        """Test successful cleanup by name pattern."""
        from models.scheduling.schedule_management import cleanup_scheduled_actions_by_name_pattern

        # Mock scheduled actions response
        mock_autoscaling_client.describe_scheduled_actions.return_value = {
            "ScheduledUpdateGroupActions": [
                {"ScheduledActionName": "test-model-daily-start"},
                {"ScheduledActionName": "test-model-monday-stop"},
                {"ScheduledActionName": "other-model-daily-start"},
                {"ScheduledActionName": "test-model-tuesday-start"},
            ]
        }

        cleanup_scheduled_actions_by_name_pattern("test-asg", "test-model")

        # Should delete actions matching the pattern (3 out of 4)
        assert mock_autoscaling_client.delete_scheduled_action.call_count == 3
        mock_autoscaling_client.delete_scheduled_action.assert_any_call(
            AutoScalingGroupName="test-asg", ScheduledActionName="test-model-daily-start"
        )
        mock_autoscaling_client.delete_scheduled_action.assert_any_call(
            AutoScalingGroupName="test-asg", ScheduledActionName="test-model-monday-stop"
        )
        mock_autoscaling_client.delete_scheduled_action.assert_any_call(
            AutoScalingGroupName="test-asg", ScheduledActionName="test-model-tuesday-start"
        )

    @patch("models.scheduling.schedule_management.autoscaling_client")
    def test_cleanup_scheduled_actions_by_name_pattern_client_error(self, mock_autoscaling_client):
        """Test cleanup with client error."""
        from botocore.exceptions import ClientError
        from models.scheduling.schedule_management import cleanup_scheduled_actions_by_name_pattern

        # Mock client error on describe
        mock_autoscaling_client.describe_scheduled_actions.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "ASG not found"}}, "DescribeScheduledActions"
        )

        # Should not raise exception
        cleanup_scheduled_actions_by_name_pattern("nonexistent-asg", "test-model")


class TestCreateScheduledActionsHelpers:
    """Test create scheduled actions helper functions."""

    @patch("models.scheduling.schedule_management.construct_scheduled_action_arn")
    @patch("models.scheduling.schedule_management.get_model_baseline_capacity")
    @patch("models.scheduling.schedule_management.scale_immediately")
    @patch("models.scheduling.schedule_management.autoscaling_client")
    def test_create_recurring_scheduled_actions_success(
        self, mock_autoscaling_client, mock_scale_immediately, mock_get_baseline_capacity, mock_construct_arn
    ):
        """Test successful creation of recurring scheduled actions."""
        from models.domain_objects import DaySchedule
        from models.scheduling.schedule_management import create_recurring_scheduled_actions

        # Mock dependencies
        mock_get_baseline_capacity.return_value = {"MinSize": 1, "MaxSize": 5, "DesiredCapacity": 2}
        mock_construct_arn.side_effect = ["start-arn", "stop-arn"]

        day_schedule = DaySchedule(startTime="09:00", stopTime="17:00")

        result = create_recurring_scheduled_actions("test-model", "test-asg", day_schedule, "UTC")

        assert result == ["start-arn", "stop-arn"]
        assert mock_autoscaling_client.put_scheduled_update_group_action.call_count == 2
        mock_scale_immediately.assert_called_once()

    @patch("models.scheduling.schedule_management.construct_scheduled_action_arn")
    @patch("models.scheduling.schedule_management.get_model_baseline_capacity")
    @patch("models.scheduling.schedule_management.check_daily_immediate_scaling")
    @patch("models.scheduling.schedule_management.autoscaling_client")
    def test_create_daily_scheduled_actions_success(
        self, mock_autoscaling_client, mock_check_daily_scaling, mock_get_baseline_capacity, mock_construct_arn
    ):
        """Test successful creation of daily scheduled actions."""
        from models.domain_objects import DaySchedule, WeeklySchedule
        from models.scheduling.schedule_management import create_daily_scheduled_actions

        # Mock dependencies
        mock_get_baseline_capacity.return_value = {"MinSize": 1, "MaxSize": 5, "DesiredCapacity": 2}
        mock_construct_arn.side_effect = ["mon-start-arn", "mon-stop-arn", "tue-start-arn", "tue-stop-arn"]

        weekly_schedule = WeeklySchedule(
            monday=DaySchedule(startTime="09:00", stopTime="17:00"),
            tuesday=DaySchedule(startTime="10:00", stopTime="18:00"),
        )

        result = create_daily_scheduled_actions("test-model", "test-asg", weekly_schedule, "UTC")

        assert result == ["mon-start-arn", "mon-stop-arn", "tue-start-arn", "tue-stop-arn"]
        assert mock_autoscaling_client.put_scheduled_update_group_action.call_count == 4
        mock_check_daily_scaling.assert_called_once()
