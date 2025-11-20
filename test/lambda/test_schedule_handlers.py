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

"""Unit tests for schedule handler classes."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from models.domain_objects import (
    DaySchedule,
    DeleteScheduleResponse,
    GetScheduleResponse,
    GetScheduleStatusResponse,
    ScheduleType,
    SchedulingConfig,
    UpdateScheduleResponse,
)
from models.exception import InvalidStateTransitionError, ModelNotFoundError
from models.handler.schedule_handlers import (
    DeleteScheduleHandler,
    GetScheduleHandler,
    GetScheduleStatusHandler,
    UpdateScheduleHandler,
)
from utilities.common_functions import user_has_group_access

# Set mock AWS credentials
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["SCHEDULE_MANAGEMENT_FUNCTION_NAME"] = "test-schedule-management-function"


@pytest.fixture
def mock_model_table():
    """Mock DynamoDB model table."""
    table = MagicMock()
    return table


@pytest.fixture
def mock_guardrails_table():
    """Mock DynamoDB guardrails table."""
    table = MagicMock()
    return table


@pytest.fixture
def mock_autoscaling_client():
    """Mock Auto Scaling client."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_stepfunctions_client():
    """Mock Step Functions client."""
    client = MagicMock()
    return client


@pytest.fixture
def mock_lambda_client():
    """Mock Lambda client."""
    client = MagicMock()
    return client


@pytest.fixture
def sample_model_item():
    """Sample model item from DynamoDB."""
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
                "nextScheduledAction": {"action": "START", "scheduledTime": "2025-01-15T09:00:00Z"},
                "lastScheduleUpdate": "2025-01-14T12:00:00Z",
            }
        },
    }


@pytest.fixture
def sample_schedule_config():
    """Sample scheduling configuration."""
    daily_schedule = DaySchedule(startTime="10:00", stopTime="18:00")
    return SchedulingConfig(
        scheduleType=ScheduleType.RECURRING, timezone="America/New_York", dailySchedule=daily_schedule
    )


class TestUpdateScheduleHandler:
    """Test UpdateScheduleHandler class."""

    def test_successful_update_schedule(
        self,
        mock_model_table,
        mock_guardrails_table,
        mock_autoscaling_client,
        mock_stepfunctions_client,
        sample_model_item,
        sample_schedule_config,
    ):
        """Test successful schedule update."""
        # Setup mock table response
        mock_model_table.get_item.return_value = {"Item": sample_model_item}

        # Setup mock lambda client response
        mock_lambda_response = {"StatusCode": 200, "Payload": MagicMock()}
        mock_lambda_response["Payload"].read.return_value = json.dumps(
            {"statusCode": 200, "body": {"message": "Schedule updated successfully"}}
        ).encode()

        with patch("boto3.client") as mock_boto3:
            mock_boto3.return_value.invoke.return_value = mock_lambda_response

            handler = UpdateScheduleHandler(
                autoscaling_client=mock_autoscaling_client,
                stepfunctions_client=mock_stepfunctions_client,
                model_table_resource=mock_model_table,
                guardrails_table_resource=mock_guardrails_table,
            )

            # Execute
            result = handler(model_id="test-model", schedule_config=sample_schedule_config)

            # Verify result
            assert isinstance(result, UpdateScheduleResponse)
            assert result.message == "Schedule updated successfully"
            assert result.modelId == "test-model"
            assert result.scheduleEnabled is True

            # Verify lambda invocation
            mock_boto3.return_value.invoke.assert_called_once()
            call_args = mock_boto3.return_value.invoke.call_args
            payload = json.loads(call_args[1]["Payload"])
            assert payload["operation"] == "update"
            assert payload["modelId"] == "test-model"
            assert payload["autoScalingGroup"] == "test-asg"

    def test_model_not_found(
        self,
        mock_model_table,
        mock_guardrails_table,
        mock_autoscaling_client,
        mock_stepfunctions_client,
        sample_schedule_config,
    ):
        """Test model not found error."""
        mock_model_table.get_item.return_value = {}

        handler = UpdateScheduleHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=mock_model_table,
            guardrails_table_resource=mock_guardrails_table,
        )

        with pytest.raises(ModelNotFoundError, match="Model test-model not found"):
            handler(model_id="test-model", schedule_config=sample_schedule_config)

    def test_invalid_model_state(
        self,
        mock_model_table,
        mock_guardrails_table,
        mock_autoscaling_client,
        mock_stepfunctions_client,
        sample_schedule_config,
    ):
        """Test invalid model state error."""
        creating_model = {"model_id": "creating-model", "model_status": "Creating"}
        mock_model_table.get_item.return_value = {"Item": creating_model}

        handler = UpdateScheduleHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=mock_model_table,
            guardrails_table_resource=mock_guardrails_table,
        )

        with pytest.raises(
            InvalidStateTransitionError, match="Cannot perform operation when model is in 'Creating' state"
        ):
            handler(model_id="creating-model", schedule_config=sample_schedule_config)

    def test_missing_autoscaling_group(
        self,
        mock_model_table,
        mock_guardrails_table,
        mock_autoscaling_client,
        mock_stepfunctions_client,
        sample_schedule_config,
    ):
        """Test missing auto scaling group error."""
        model_without_asg = {
            "model_id": "test-model",
            "model_status": "InService",
            # Missing auto_scaling_group
        }
        mock_model_table.get_item.return_value = {"Item": model_without_asg}

        handler = UpdateScheduleHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=mock_model_table,
            guardrails_table_resource=mock_guardrails_table,
        )

        with pytest.raises(ValueError, match="Model does not have an Auto Scaling Group configured"):
            handler(model_id="test-model", schedule_config=sample_schedule_config)

    def test_lambda_invocation_failure(
        self,
        mock_model_table,
        mock_guardrails_table,
        mock_autoscaling_client,
        mock_stepfunctions_client,
        sample_model_item,
        sample_schedule_config,
    ):
        """Test Lambda invocation failure."""
        mock_model_table.get_item.return_value = {"Item": sample_model_item}

        # Setup mock lambda failure response
        mock_lambda_response = {"StatusCode": 500, "Payload": MagicMock()}
        mock_lambda_response["Payload"].read.return_value = json.dumps(
            {"statusCode": 500, "body": {"message": "Internal server error"}}
        ).encode()

        with patch("boto3.client") as mock_boto3:
            mock_boto3.return_value.invoke.return_value = mock_lambda_response

            handler = UpdateScheduleHandler(
                autoscaling_client=mock_autoscaling_client,
                stepfunctions_client=mock_stepfunctions_client,
                model_table_resource=mock_model_table,
                guardrails_table_resource=mock_guardrails_table,
            )

            with pytest.raises(ValueError, match="Failed to create/update schedule"):
                handler(model_id="test-model", schedule_config=sample_schedule_config)


class TestGetScheduleHandler:
    """Test GetScheduleHandler class."""

    def test_successful_get_schedule(
        self,
        mock_model_table,
        mock_guardrails_table,
        mock_autoscaling_client,
        mock_stepfunctions_client,
        sample_model_item,
    ):
        """Test successful schedule retrieval."""
        mock_model_table.get_item.return_value = {"Item": sample_model_item}

        # Setup mock lambda response
        schedule_data = {
            "scheduling": {
                "scheduleType": "RECURRING",
                "timezone": "UTC",
                "dailySchedule": {"startTime": "09:00", "stopTime": "17:00"},
            },
            "nextScheduledAction": {"action": "START", "scheduledTime": "2025-01-15T09:00:00Z"},
        }

        mock_lambda_response = {"StatusCode": 200, "Payload": MagicMock()}
        mock_lambda_response["Payload"].read.return_value = json.dumps(
            {"statusCode": 200, "body": json.dumps(schedule_data)}
        ).encode()

        with patch("boto3.client") as mock_boto3:
            mock_boto3.return_value.invoke.return_value = mock_lambda_response

            handler = GetScheduleHandler(
                autoscaling_client=mock_autoscaling_client,
                stepfunctions_client=mock_stepfunctions_client,
                model_table_resource=mock_model_table,
                guardrails_table_resource=mock_guardrails_table,
            )

            # Execute
            result = handler(model_id="test-model")

            # Verify result
            assert isinstance(result, GetScheduleResponse)
            assert result.modelId == "test-model"
            assert result.scheduling == schedule_data["scheduling"]
            assert result.nextScheduledAction == schedule_data["nextScheduledAction"]

    def test_model_not_found(
        self, mock_model_table, mock_guardrails_table, mock_autoscaling_client, mock_stepfunctions_client
    ):
        """Test model not found error."""
        mock_model_table.get_item.return_value = {}

        handler = GetScheduleHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=mock_model_table,
            guardrails_table_resource=mock_guardrails_table,
        )

        with pytest.raises(ModelNotFoundError, match="Model test-model not found"):
            handler(model_id="test-model")


class TestDeleteScheduleHandler:
    """Test DeleteScheduleHandler class."""

    def test_successful_delete_schedule(
        self,
        mock_model_table,
        mock_guardrails_table,
        mock_autoscaling_client,
        mock_stepfunctions_client,
        sample_model_item,
    ):
        """Test successful schedule deletion."""
        mock_model_table.get_item.return_value = {"Item": sample_model_item}

        # Setup mock lambda response
        mock_lambda_response = {"StatusCode": 200, "Payload": MagicMock()}
        mock_lambda_response["Payload"].read.return_value = json.dumps(
            {"statusCode": 200, "body": {"message": "Schedule deleted successfully"}}
        ).encode()

        with patch("boto3.client") as mock_boto3:
            mock_boto3.return_value.invoke.return_value = mock_lambda_response

            handler = DeleteScheduleHandler(
                autoscaling_client=mock_autoscaling_client,
                stepfunctions_client=mock_stepfunctions_client,
                model_table_resource=mock_model_table,
                guardrails_table_resource=mock_guardrails_table,
            )

            # Execute
            result = handler(model_id="test-model")

            # Verify result
            assert isinstance(result, DeleteScheduleResponse)
            assert result.message == "Schedule deleted successfully"
            assert result.modelId == "test-model"
            assert result.scheduleEnabled is False

    def test_invalid_model_state(
        self, mock_model_table, mock_guardrails_table, mock_autoscaling_client, mock_stepfunctions_client
    ):
        """Test invalid model state error."""
        creating_model = {"model_id": "creating-model", "model_status": "Creating"}
        mock_model_table.get_item.return_value = {"Item": creating_model}

        handler = DeleteScheduleHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=mock_model_table,
            guardrails_table_resource=mock_guardrails_table,
        )

        with pytest.raises(
            InvalidStateTransitionError, match="Cannot perform operation when model is in 'Creating' state"
        ):
            handler(model_id="creating-model")


class TestGetScheduleStatusHandler:
    """Test GetScheduleStatusHandler class."""

    def test_successful_get_schedule_status(
        self,
        mock_model_table,
        mock_guardrails_table,
        mock_autoscaling_client,
        mock_stepfunctions_client,
        sample_model_item,
    ):
        """Test successful schedule status retrieval."""
        mock_model_table.get_item.return_value = {"Item": sample_model_item}

        handler = GetScheduleStatusHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=mock_model_table,
            guardrails_table_resource=mock_guardrails_table,
        )

        # Execute
        result = handler(model_id="test-model")

        # Verify result
        assert isinstance(result, GetScheduleStatusResponse)
        assert result.modelId == "test-model"
        assert result.scheduleEnabled is True
        assert result.scheduleConfigured is True
        assert result.lastScheduleFailed is False
        assert result.scheduleStatus == "ACTIVE"
        assert result.scheduleType == "RECURRING"
        assert result.timezone == "UTC"

    def test_schedule_status_disabled(
        self, mock_model_table, mock_guardrails_table, mock_autoscaling_client, mock_stepfunctions_client
    ):
        """Test schedule status when schedule is disabled."""
        model_no_schedule = {
            "model_id": "test-model",
            "autoScalingConfig": {"scheduling": {"scheduleConfigured": False, "lastScheduleFailed": False}},
        }
        mock_model_table.get_item.return_value = {"Item": model_no_schedule}

        handler = GetScheduleStatusHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=mock_model_table,
            guardrails_table_resource=mock_guardrails_table,
        )

        # Execute
        result = handler(model_id="test-model")

        # Verify result
        assert result.scheduleStatus == "DISABLED"
        assert result.scheduleConfigured is False

    def test_schedule_status_failed(
        self, mock_model_table, mock_guardrails_table, mock_autoscaling_client, mock_stepfunctions_client
    ):
        """Test schedule status when schedule has failed."""
        model_failed_schedule = {
            "model_id": "test-model",
            "autoScalingConfig": {
                "scheduling": {
                    "scheduleConfigured": True,
                    "lastScheduleFailed": True,
                    "scheduleType": "RECURRING",
                    "timezone": "UTC",
                }
            },
        }
        mock_model_table.get_item.return_value = {"Item": model_failed_schedule}

        handler = GetScheduleStatusHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=mock_model_table,
            guardrails_table_resource=mock_guardrails_table,
        )

        # Execute
        result = handler(model_id="test-model")

        # Verify result
        assert result.scheduleStatus == "FAILED"
        assert result.lastScheduleFailed is True

    def test_model_without_scheduling_config(
        self, mock_model_table, mock_guardrails_table, mock_autoscaling_client, mock_stepfunctions_client
    ):
        """Test model without scheduling configuration."""
        model_no_scheduling = {"model_id": "test-model", "autoScalingConfig": {}}
        mock_model_table.get_item.return_value = {"Item": model_no_scheduling}

        handler = GetScheduleStatusHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=mock_model_table,
            guardrails_table_resource=mock_guardrails_table,
        )

        # Execute
        result = handler(model_id="test-model")

        # Verify result
        assert result.scheduleEnabled is False
        assert result.scheduleConfigured is False
        assert result.scheduleStatus == "DISABLED"
        assert result.scheduleType is None
        assert result.timezone == "UTC"

    def test_model_not_found(
        self, mock_model_table, mock_guardrails_table, mock_autoscaling_client, mock_stepfunctions_client
    ):
        """Test model not found error."""
        mock_model_table.get_item.return_value = {}

        handler = GetScheduleStatusHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=mock_model_table,
            guardrails_table_resource=mock_guardrails_table,
        )

        with pytest.raises(ModelNotFoundError, match="Model test-model not found"):
            handler(model_id="test-model")


class TestUserGroupAccess:
    """Test user group access functionality."""

    def test_user_has_group_access_with_matching_groups(self):
        """Test user has access when groups match."""
        user_groups = ["admin", "developers"]
        allowed_groups = ["developers", "testers"]

        assert user_has_group_access(user_groups, allowed_groups) is True

    def test_user_has_group_access_with_no_matching_groups(self):
        """Test user has no access when groups don't match."""
        user_groups = ["admin", "managers"]
        allowed_groups = ["developers", "testers"]

        assert user_has_group_access(user_groups, allowed_groups) is False

    def test_user_has_group_access_with_empty_allowed_groups(self):
        """Test user has access when no groups are specified."""
        user_groups = ["admin"]
        allowed_groups = []

        assert user_has_group_access(user_groups, allowed_groups) is True

    def test_user_has_group_access_with_empty_user_groups(self):
        """Test user has no access when user has no groups."""
        user_groups = []
        allowed_groups = ["developers"]

        assert user_has_group_access(user_groups, allowed_groups) is False


class TestUpdateScheduleHandlerGroupAccess:
    """Test UpdateScheduleHandler with group access controls."""

    def test_update_schedule_with_group_access_allowed(
        self,
        mock_model_table,
        mock_guardrails_table,
        mock_autoscaling_client,
        mock_stepfunctions_client,
        sample_schedule_config,
    ):
        """Test successful update with group access."""
        # Setup model with allowed groups
        model_item = {
            "model_id": "test-model",
            "model_status": "InService",
            "auto_scaling_group": "test-asg",
            "allowedGroups": ["developers", "admins"],
        }
        mock_model_table.get_item.return_value = {"Item": model_item}

        # Setup mock lambda response
        mock_lambda_response = {"StatusCode": 200, "Payload": MagicMock()}
        mock_lambda_response["Payload"].read.return_value = json.dumps(
            {"statusCode": 200, "body": {"message": "Schedule updated successfully"}}
        ).encode()

        with patch("boto3.client") as mock_boto3:
            mock_boto3.return_value.invoke.return_value = mock_lambda_response

            handler = UpdateScheduleHandler(
                autoscaling_client=mock_autoscaling_client,
                stepfunctions_client=mock_stepfunctions_client,
                model_table_resource=mock_model_table,
                guardrails_table_resource=mock_guardrails_table,
            )

            # Execute with matching user groups
            result = handler(
                model_id="test-model",
                schedule_config=sample_schedule_config,
                user_groups=["developers", "testers"],
                is_admin=False,
            )

            # Verify result
            assert isinstance(result, UpdateScheduleResponse)
            assert result.message == "Schedule updated successfully"

    def test_update_schedule_with_group_access_denied(
        self,
        mock_model_table,
        mock_guardrails_table,
        mock_autoscaling_client,
        mock_stepfunctions_client,
        sample_schedule_config,
    ):
        """Test update denied due to group access."""
        # Setup model with allowed groups
        model_item = {
            "model_id": "test-model",
            "model_status": "InService",
            "auto_scaling_group": "test-asg",
            "allowedGroups": ["developers", "admins"],
        }
        mock_model_table.get_item.return_value = {"Item": model_item}

        handler = UpdateScheduleHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=mock_model_table,
            guardrails_table_resource=mock_guardrails_table,
        )

        # Execute with non-matching user groups
        with pytest.raises(ModelNotFoundError, match="Model test-model not found"):
            handler(
                model_id="test-model",
                schedule_config=sample_schedule_config,
                user_groups=["testers", "managers"],
                is_admin=False,
            )

    def test_update_schedule_admin_bypass_group_access(
        self,
        mock_model_table,
        mock_guardrails_table,
        mock_autoscaling_client,
        mock_stepfunctions_client,
        sample_schedule_config,
    ):
        """Test admin can bypass group access restrictions."""
        # Setup model with allowed groups
        model_item = {
            "model_id": "test-model",
            "model_status": "InService",
            "auto_scaling_group": "test-asg",
            "allowedGroups": ["developers"],
        }
        mock_model_table.get_item.return_value = {"Item": model_item}

        # Setup mock lambda response
        mock_lambda_response = {"StatusCode": 200, "Payload": MagicMock()}
        mock_lambda_response["Payload"].read.return_value = json.dumps(
            {"statusCode": 200, "body": {"message": "Schedule updated successfully"}}
        ).encode()

        with patch("boto3.client") as mock_boto3:
            mock_boto3.return_value.invoke.return_value = mock_lambda_response

            handler = UpdateScheduleHandler(
                autoscaling_client=mock_autoscaling_client,
                stepfunctions_client=mock_stepfunctions_client,
                model_table_resource=mock_model_table,
                guardrails_table_resource=mock_guardrails_table,
            )

            # Execute as admin with non-matching groups
            result = handler(
                model_id="test-model", schedule_config=sample_schedule_config, user_groups=["managers"], is_admin=True
            )

            # Verify result
            assert isinstance(result, UpdateScheduleResponse)
            assert result.message == "Schedule updated successfully"


class TestGetScheduleHandlerGroupAccess:
    """Test GetScheduleHandler with group access controls."""

    def test_get_schedule_with_group_access_denied(
        self, mock_model_table, mock_guardrails_table, mock_autoscaling_client, mock_stepfunctions_client
    ):
        """Test get schedule denied due to group access."""
        # Setup model with allowed groups
        model_item = {
            "model_id": "test-model",
            "allowedGroups": ["developers"],
        }
        mock_model_table.get_item.return_value = {"Item": model_item}

        handler = GetScheduleHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=mock_model_table,
            guardrails_table_resource=mock_guardrails_table,
        )

        # Execute with non-matching user groups
        with pytest.raises(ModelNotFoundError, match="Model test-model not found"):
            handler(model_id="test-model", user_groups=["managers"], is_admin=False)


class TestDeleteScheduleHandlerGroupAccess:
    """Test DeleteScheduleHandler with group access controls."""

    def test_delete_schedule_with_group_access_denied(
        self, mock_model_table, mock_guardrails_table, mock_autoscaling_client, mock_stepfunctions_client
    ):
        """Test delete schedule denied due to group access."""
        # Setup model with allowed groups
        model_item = {
            "model_id": "test-model",
            "allowedGroups": ["developers"],
        }
        mock_model_table.get_item.return_value = {"Item": model_item}

        handler = DeleteScheduleHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=mock_model_table,
            guardrails_table_resource=mock_guardrails_table,
        )

        # Execute with non-matching user groups
        with pytest.raises(ModelNotFoundError, match="Model test-model not found"):
            handler(model_id="test-model", user_groups=["managers"], is_admin=False)


class TestGetScheduleStatusHandlerGroupAccess:
    """Test GetScheduleStatusHandler with group access controls."""

    def test_get_schedule_status_with_group_access_denied(
        self, mock_model_table, mock_guardrails_table, mock_autoscaling_client, mock_stepfunctions_client
    ):
        """Test get schedule status denied due to group access."""
        # Setup model with allowed groups
        model_item = {
            "model_id": "test-model",
            "allowedGroups": ["developers"],
        }
        mock_model_table.get_item.return_value = {"Item": model_item}

        handler = GetScheduleStatusHandler(
            autoscaling_client=mock_autoscaling_client,
            stepfunctions_client=mock_stepfunctions_client,
            model_table_resource=mock_model_table,
            guardrails_table_resource=mock_guardrails_table,
        )

        # Execute with non-matching user groups
        with pytest.raises(ModelNotFoundError, match="Model test-model not found"):
            handler(model_id="test-model", user_groups=["managers"], is_admin=False)


class TestLambdaInvocationErrorHandling:
    """Test Lambda invocation error handling scenarios."""

    def test_update_schedule_lambda_error_response_format_string_body(
        self,
        mock_model_table,
        mock_guardrails_table,
        mock_autoscaling_client,
        mock_stepfunctions_client,
        sample_model_item,
        sample_schedule_config,
    ):
        """Test Lambda error response with string body format."""
        mock_model_table.get_item.return_value = {"Item": sample_model_item}

        # Setup mock lambda error response with string body
        mock_lambda_response = {"StatusCode": 500, "Payload": MagicMock()}
        mock_lambda_response["Payload"].read.return_value = json.dumps(
            {"statusCode": 500, "body": "Internal server error"}
        ).encode()

        with patch("boto3.client") as mock_boto3:
            mock_boto3.return_value.invoke.return_value = mock_lambda_response

            handler = UpdateScheduleHandler(
                autoscaling_client=mock_autoscaling_client,
                stepfunctions_client=mock_stepfunctions_client,
                model_table_resource=mock_model_table,
                guardrails_table_resource=mock_guardrails_table,
            )

            with pytest.raises(ValueError, match="Failed to create/update schedule: Internal server error"):
                handler(model_id="test-model", schedule_config=sample_schedule_config)

    def test_update_schedule_lambda_invalid_json_body(
        self,
        mock_model_table,
        mock_guardrails_table,
        mock_autoscaling_client,
        mock_stepfunctions_client,
        sample_model_item,
        sample_schedule_config,
    ):
        """Test Lambda error response with invalid JSON body."""
        mock_model_table.get_item.return_value = {"Item": sample_model_item}

        # Setup mock lambda error response with invalid JSON
        mock_lambda_response = {"StatusCode": 500, "Payload": MagicMock()}
        mock_lambda_response["Payload"].read.return_value = json.dumps(
            {"statusCode": 500, "body": "invalid json {"}
        ).encode()

        with patch("boto3.client") as mock_boto3:
            mock_boto3.return_value.invoke.return_value = mock_lambda_response

            handler = UpdateScheduleHandler(
                autoscaling_client=mock_autoscaling_client,
                stepfunctions_client=mock_stepfunctions_client,
                model_table_resource=mock_model_table,
                guardrails_table_resource=mock_guardrails_table,
            )

            with pytest.raises(ValueError, match="Failed to create/update schedule: invalid json"):
                handler(model_id="test-model", schedule_config=sample_schedule_config)

    def test_get_schedule_lambda_error_handling(
        self,
        mock_model_table,
        mock_guardrails_table,
        mock_autoscaling_client,
        mock_stepfunctions_client,
        sample_model_item,
    ):
        """Test GetSchedule Lambda error handling."""
        mock_model_table.get_item.return_value = {"Item": sample_model_item}

        # Setup mock lambda error response
        mock_lambda_response = {"StatusCode": 500, "Payload": MagicMock()}
        mock_lambda_response["Payload"].read.return_value = json.dumps(
            {"statusCode": 500, "body": {"message": "Lambda execution failed"}}
        ).encode()

        with patch("boto3.client") as mock_boto3:
            mock_boto3.return_value.invoke.return_value = mock_lambda_response

            handler = GetScheduleHandler(
                autoscaling_client=mock_autoscaling_client,
                stepfunctions_client=mock_stepfunctions_client,
                model_table_resource=mock_model_table,
                guardrails_table_resource=mock_guardrails_table,
            )

            with pytest.raises(ValueError, match="Failed to get schedule: Lambda execution failed"):
                handler(model_id="test-model")

    def test_delete_schedule_lambda_error_handling(
        self,
        mock_model_table,
        mock_guardrails_table,
        mock_autoscaling_client,
        mock_stepfunctions_client,
        sample_model_item,
    ):
        """Test DeleteSchedule Lambda error handling."""
        mock_model_table.get_item.return_value = {"Item": sample_model_item}

        # Setup mock lambda error response
        mock_lambda_response = {"StatusCode": 500, "Payload": MagicMock()}
        mock_lambda_response["Payload"].read.return_value = json.dumps(
            {"statusCode": 500, "body": {"message": "Lambda execution failed"}}
        ).encode()

        with patch("boto3.client") as mock_boto3:
            mock_boto3.return_value.invoke.return_value = mock_lambda_response

            handler = DeleteScheduleHandler(
                autoscaling_client=mock_autoscaling_client,
                stepfunctions_client=mock_stepfunctions_client,
                model_table_resource=mock_model_table,
                guardrails_table_resource=mock_guardrails_table,
            )

            with pytest.raises(ValueError, match="Failed to delete schedule: Lambda execution failed"):
                handler(model_id="test-model")
