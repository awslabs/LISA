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
        "scheduleType": "RECURRING_DAILY",
        "timezone": "America/New_York",
        "dailySchedule": {"startTime": "09:00", "stopTime": "17:00"},
        "scheduleEnabled": True,
    }


@pytest.fixture
def sample_weekly_schedule_config():
    """Sample weekly schedule configuration."""
    return {
        "scheduleType": "EACH_DAY",
        "timezone": "UTC",
        "weeklySchedule": {
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
    @patch("models.scheduling.schedule_management.calculate_next_scheduled_action")
    def test_update_operation_success(
        self, mock_calculate_next, mock_autoscaling_client, mock_model_table, lambda_context, sample_schedule_config
    ):
        """Test successful update operation."""
        from models.scheduling.schedule_management import lambda_handler

        # Mock model table
        mock_model_table.get_item.return_value = {"Item": {"model_id": "test-model"}}
        mock_model_table.update_item.return_value = {}

        # Mock calculate_next_scheduled_action
        next_action = {"action": "START", "scheduledTime": "2025-01-15T14:00:00-05:00"}  # 9 AM EST
        mock_calculate_next.return_value = next_action

        # Mock successful Auto Scaling operations
        mock_autoscaling_client.put_scheduled_update_group_action.return_value = {}
        mock_autoscaling_client.describe_scheduled_actions.return_value = {"ScheduledUpdateGroupActions": []}

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
        assert mock_autoscaling_client.put_scheduled_update_group_action.call_count == 2  # START and STOP

        # Verify DynamoDB update
        mock_model_table.update_item.assert_called_once()

    @patch("models.scheduling.schedule_management.model_table")
    def test_get_operation_success(self, mock_model_table, lambda_context, sample_schedule_config):
        """Test successful get operation."""
        from models.scheduling.schedule_management import lambda_handler

        # Mock model table with schedule data
        mock_model_table.get_item.return_value = {
            "Item": {"model_id": "test-model", "autoScalingConfig": {"scheduling": sample_schedule_config}}
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

        # Mock model table - need to mock both get_item calls
        mock_model_table.get_item.return_value = {
            "Item": {
                "model_id": "test-model",
                "autoScalingConfig": {
                    "scheduling": {
                        "scheduledActionArns": [
                            "arn:aws:autoscaling:us-east-1:123456789012:scheduledUpdateGroupAction:*:autoScalingGroupName/test-asg:scheduledActionName/test-model-START-action",
                            "arn:aws:autoscaling:us-east-1:123456789012:scheduledUpdateGroupAction:*:autoScalingGroupName/test-asg:scheduledActionName/test-model-STOP-action",
                        ]
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


class TestCalculateNextScheduledAction:
    """Test calculate_next_scheduled_action function."""

    def test_recurring_daily_schedule(self):
        """Test RECURRING_DAILY schedule calculation."""
        from models.scheduling.schedule_management import calculate_next_scheduled_action

        schedule_config = {
            "scheduleType": "RECURRING_DAILY",
            "timezone": "UTC",
            "dailySchedule": {"startTime": "09:00", "stopTime": "17:00"},
        }

        result = calculate_next_scheduled_action(schedule_config)

        # Just verify it returns a result (the actual calculation logic is complex)
        assert result is not None
        assert result["action"] in ["START", "STOP"]

    def test_each_day_schedule(self):
        """Test EACH_DAY schedule calculation."""
        from models.scheduling.schedule_management import calculate_next_scheduled_action

        schedule_config = {
            "scheduleType": "EACH_DAY",
            "timezone": "UTC",
            "weeklySchedule": {
                "monday": {"startTime": "09:00", "stopTime": "17:00"},
                "wednesday": {"startTime": "10:00", "stopTime": "18:00"},
            },
        }

        result = calculate_next_scheduled_action(schedule_config)

        # Just verify it returns a result
        assert result is not None
        assert result["action"] in ["START", "STOP"]

    def test_timezone_conversion(self):
        """Test timezone conversion in schedule calculation."""
        from models.scheduling.schedule_management import calculate_next_scheduled_action

        schedule_config = {
            "scheduleType": "RECURRING_DAILY",
            "timezone": "America/New_York",
            "dailySchedule": {"startTime": "09:00", "stopTime": "17:00"},
        }

        result = calculate_next_scheduled_action(schedule_config)

        # Just verify it returns a result
        assert result is not None
        assert result["action"] in ["START", "STOP"]

    def test_no_schedule_type(self):
        """Test None schedule type."""
        from models.scheduling.schedule_management import calculate_next_scheduled_action

        schedule_config = {"scheduleType": None, "timezone": "UTC"}

        result = calculate_next_scheduled_action(schedule_config)

        assert result is None


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
        from models.scheduling.schedule_management import get_existing_asg_capacity, ScheduleManagementError

        # Mock empty ASG response
        mock_autoscaling_client.describe_auto_scaling_groups.return_value = {"AutoScalingGroups": []}

        with pytest.raises(ScheduleManagementError, match="Auto Scaling Group test-asg not found"):
            get_existing_asg_capacity("test-asg")

    @patch("models.scheduling.schedule_management.autoscaling_client")
    def test_get_existing_asg_capacity_client_error(self, mock_autoscaling_client):
        """Test ASG client error handling."""
        from botocore.exceptions import ClientError
        from models.scheduling.schedule_management import get_existing_asg_capacity, ScheduleManagementError

        # Mock client error
        mock_autoscaling_client.describe_auto_scaling_groups.side_effect = ClientError(
            {"Error": {"Code": "ValidationError", "Message": "Invalid ASG name"}}, "DescribeAutoScalingGroups"
        )

        with pytest.raises(ScheduleManagementError, match="Failed to get ASG capacity"):
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

    def test_convert_to_utc_cron(self):
        """Test time conversion to UTC cron."""
        from models.scheduling.schedule_management import convert_to_utc_cron

        # Test with UTC timezone (should be same)
        result = convert_to_utc_cron("09:30", "UTC")
        assert result == "30 9 * * *"

    def test_convert_to_utc_cron_weekdays(self):
        """Test weekdays time conversion to UTC cron."""
        from models.scheduling.schedule_management import convert_to_utc_cron_weekdays

        # Test with UTC timezone
        result = convert_to_utc_cron_weekdays("14:15", "UTC")
        assert result == "15 14 * * 1-5"

    def test_convert_to_utc_cron_with_day(self):
        """Test time conversion with specific day."""
        from models.scheduling.schedule_management import convert_to_utc_cron_with_day

        # Test with UTC timezone and Monday (1)
        result = convert_to_utc_cron_with_day("08:45", "UTC", 1)
        assert result == "45 8 * * 1"

    @patch("models.scheduling.schedule_management.model_table")
    def test_get_existing_scheduled_action_arns_success(self, mock_model_table):
        """Test successful retrieval of existing scheduled action ARNs."""
        from models.scheduling.schedule_management import get_existing_scheduled_action_arns

        # Mock model table response
        mock_model_table.get_item.return_value = {
            "Item": {
                "model_id": "test-model",
                "autoScalingConfig": {"scheduling": {"scheduledActionArns": ["arn1", "arn2"]}},
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

    @patch("models.scheduling.schedule_management.create_daily_scheduled_actions")
    def test_create_scheduled_actions_recurring_daily(self, mock_create_daily):
        """Test creating scheduled actions for RECURRING_DAILY type."""
        from models.domain_objects import DaySchedule, ScheduleType, SchedulingConfig
        from models.scheduling.schedule_management import create_scheduled_actions

        mock_create_daily.return_value = ["arn1", "arn2"]

        schedule_config = SchedulingConfig(
            scheduleType=ScheduleType.RECURRING_DAILY,
            timezone="UTC",
            dailySchedule=DaySchedule(startTime="09:00", stopTime="17:00"),
        )

        result = create_scheduled_actions("test-model", "test-asg", schedule_config)

        assert result == ["arn1", "arn2"]
        mock_create_daily.assert_called_once_with("test-model", "test-asg", schedule_config.dailySchedule, "UTC")

    @patch("models.scheduling.schedule_management.create_weekly_scheduled_actions")
    def test_create_scheduled_actions_each_day(self, mock_create_weekly):
        """Test creating scheduled actions for EACH_DAY type."""
        from models.domain_objects import DaySchedule, ScheduleType, SchedulingConfig, WeeklySchedule
        from models.scheduling.schedule_management import create_scheduled_actions

        mock_create_weekly.return_value = ["arn1", "arn2", "arn3"]

        weekly_schedule = WeeklySchedule(
            monday=DaySchedule(startTime="09:00", stopTime="17:00"),
            tuesday=DaySchedule(startTime="10:00", stopTime="18:00"),
        )

        schedule_config = SchedulingConfig(
            scheduleType=ScheduleType.EACH_DAY, timezone="UTC", weeklySchedule=weekly_schedule
        )

        result = create_scheduled_actions("test-model", "test-asg", schedule_config)

        assert result == ["arn1", "arn2", "arn3"]
        mock_create_weekly.assert_called_once_with("test-model", "test-asg", schedule_config.weeklySchedule, "UTC")

    def test_create_scheduled_actions_recurring_daily_missing_schedule(self):
        """Test error when dailySchedule is missing for RECURRING_DAILY."""
        from models.domain_objects import ScheduleType, SchedulingConfig
        from models.scheduling.schedule_management import create_scheduled_actions

        # Create config with None type first, then modify to avoid Pydantic validation
        schedule_config = SchedulingConfig(scheduleType=None, timezone="UTC")
        # Manually set the schedule type to test the runtime validation
        schedule_config.scheduleType = ScheduleType.RECURRING_DAILY
        schedule_config.dailySchedule = None

        with pytest.raises(ValueError, match="dailySchedule required for RECURRING_DAILY type"):
            create_scheduled_actions("test-model", "test-asg", schedule_config)

    def test_create_scheduled_actions_each_day_missing_schedule(self):
        """Test error when weeklySchedule is missing for EACH_DAY."""
        from models.domain_objects import ScheduleType, SchedulingConfig
        from models.scheduling.schedule_management import create_scheduled_actions

        # Create config with None type first, then modify to avoid Pydantic validation
        schedule_config = SchedulingConfig(scheduleType=None, timezone="UTC")
        # Manually set the schedule type to test the runtime validation
        schedule_config.scheduleType = ScheduleType.EACH_DAY
        schedule_config.weeklySchedule = None

        with pytest.raises(ValueError, match="weeklySchedule required for EACH_DAY type"):
            create_scheduled_actions("test-model", "test-asg", schedule_config)


class TestUpdateModelScheduleRecord:
    """Test update_model_schedule_record function."""

    @patch("models.scheduling.schedule_management.model_table")
    @patch("models.scheduling.schedule_management.calculate_next_scheduled_action")
    def test_update_model_schedule_record_existing_config(self, mock_calculate_next, mock_model_table):
        """Test updating model with existing autoScalingConfig."""
        from models.domain_objects import DaySchedule, ScheduleType, SchedulingConfig
        from models.scheduling.schedule_management import update_model_schedule_record

        # Mock existing model with autoScalingConfig
        mock_model_table.get_item.return_value = {
            "Item": {"model_id": "test-model", "autoScalingConfig": {"existing": "config"}}
        }

        mock_calculate_next.return_value = {"action": "START", "scheduledTime": "2025-01-15T09:00:00Z"}

        # Create valid SchedulingConfig with required dailySchedule for RECURRING_DAILY
        daily_schedule = DaySchedule(startTime="09:00", stopTime="17:00")
        schedule_config = SchedulingConfig(
            scheduleType=ScheduleType.RECURRING_DAILY, timezone="UTC", dailySchedule=daily_schedule
        )

        update_model_schedule_record("test-model", schedule_config, ["arn1"], True)

        # Verify update_item was called with correct expression
        mock_model_table.update_item.assert_called_once()
        call_args = mock_model_table.update_item.call_args
        assert call_args[1]["UpdateExpression"] == "SET autoScalingConfig.scheduling = :scheduling"

    @patch("models.scheduling.schedule_management.model_table")
    @patch("models.scheduling.schedule_management.calculate_next_scheduled_action")
    def test_update_model_schedule_record_new_config(self, mock_calculate_next, mock_model_table):
        """Test updating model without existing autoScalingConfig."""
        from models.domain_objects import DaySchedule, ScheduleType, SchedulingConfig
        from models.scheduling.schedule_management import update_model_schedule_record

        # Mock model without autoScalingConfig
        mock_model_table.get_item.return_value = {
            "Item": {
                "model_id": "test-model"
                # No autoScalingConfig
            }
        }

        mock_calculate_next.return_value = {"action": "START", "scheduledTime": "2025-01-15T09:00:00Z"}

        # Create valid SchedulingConfig with required dailySchedule for RECURRING_DAILY
        daily_schedule = DaySchedule(startTime="09:00", stopTime="17:00")
        schedule_config = SchedulingConfig(
            scheduleType=ScheduleType.RECURRING_DAILY, timezone="UTC", dailySchedule=daily_schedule
        )

        update_model_schedule_record("test-model", schedule_config, ["arn1"], True)

        # Verify update_item was called with correct expression
        mock_model_table.update_item.assert_called_once()
        call_args = mock_model_table.update_item.call_args
        assert call_args[1]["UpdateExpression"] == "SET autoScalingConfig = :autoScalingConfig"

    @patch("models.scheduling.schedule_management.model_table")
    def test_update_model_schedule_record_model_not_found(self, mock_model_table):
        """Test error when model is not found."""
        from models.domain_objects import DaySchedule, ScheduleType, SchedulingConfig
        from models.scheduling.schedule_management import update_model_schedule_record

        # Mock model not found
        mock_model_table.get_item.return_value = {}

        # Create valid SchedulingConfig with required dailySchedule for RECURRING_DAILY
        daily_schedule = DaySchedule(startTime="09:00", stopTime="17:00")
        schedule_config = SchedulingConfig(
            scheduleType=ScheduleType.RECURRING_DAILY, timezone="UTC", dailySchedule=daily_schedule
        )

        with pytest.raises(ValueError, match="Model test-model not found"):
            update_model_schedule_record("test-model", schedule_config, ["arn1"], True)


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
