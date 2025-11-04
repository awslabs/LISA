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

import json
import os
from typing import Any, List, Optional

import boto3
from utilities.common_functions import retry_config

from ..domain_objects import (
    DeleteScheduleResponse,
    GetScheduleResponse,
    GetScheduleStatusResponse,
    SchedulingConfig,
    UpdateScheduleResponse,
)
from ..exception import InvalidStateTransitionError, ModelNotFoundError
from .base_handler import BaseApiHandler


def user_has_group_access(user_groups: List[str], allowed_groups: List[str]) -> bool:
    """Check if user has access based on group membership"""
    if not allowed_groups:  # If no groups specified, allow access
        return True
    return bool(set(user_groups) & set(allowed_groups))


class ScheduleBaseHandler(BaseApiHandler):
    """Base handler for schedule operations with Lambda client"""

    def __init__(self, autoscaling_client: Any, stepfunctions_client: Any, model_table_resource: Any):
        """Initialize with Lambda client for schedule management operations"""
        super().__init__(autoscaling_client, stepfunctions_client, model_table_resource)
        self._lambda_client = boto3.client("lambda", region_name=os.environ["AWS_REGION"], config=retry_config)


class UpdateScheduleHandler(ScheduleBaseHandler):
    """Handler class for UpdateSchedule requests"""

    def __call__(
        self,
        model_id: str,
        schedule_config: SchedulingConfig,
        user_groups: Optional[List[str]] = None,
        is_admin: bool = False,
    ) -> UpdateScheduleResponse:
        """Create or update a schedule for a model"""
        # Validate model exists and is in correct state
        model_response = self._model_table.get_item(Key={"model_id": model_id})
        if "Item" not in model_response:
            raise ModelNotFoundError(f"Model {model_id} not found")

        model_item = model_response["Item"]

        # Check if user has access to this model based on groups
        if not is_admin and user_groups is not None:
            allowed_groups = model_item.get("allowedGroups", [])
            if not user_has_group_access(user_groups, allowed_groups):
                raise ModelNotFoundError(f"Model {model_id} not found")

        model_status = model_item.get("model_status")

        allowed_statuses = ["InService", "Stopped"]
        if model_status not in allowed_statuses:
            raise InvalidStateTransitionError(
                f"Cannot edit schedule when model is in '{model_status}' state, model must be InService or Stopped."
            )

        # Get Auto Scaling Group name from model
        auto_scaling_group = model_item.get("auto_scaling_group")
        if not auto_scaling_group:
            raise ValueError("Model does not have an Auto Scaling Group configured")

        # Invoke Schedule Management Lambda
        payload = {
            "operation": "update",
            "modelId": model_id,
            "scheduleConfig": schedule_config.model_dump(),
            "autoScalingGroup": auto_scaling_group,
        }

        response = self._lambda_client.invoke(
            FunctionName=os.environ.get("SCHEDULE_MANAGEMENT_FUNCTION_NAME"),
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )

        result = json.loads(response["Payload"].read())

        if response["StatusCode"] != 200 or result.get("statusCode") != 200:
            # Handle both string and dict body formats
            body = result.get("body", "Unknown error")
            if isinstance(body, str):
                try:
                    body_dict = json.loads(body)
                    error_message = body_dict.get("message", body)
                except json.JSONDecodeError:
                    error_message = body
            else:
                error_message = body.get("message", "Unknown error") if isinstance(body, dict) else str(body)
            raise ValueError(f"Failed to create/update schedule: {error_message}")

        return UpdateScheduleResponse(message="Schedule updated successfully", modelId=model_id, scheduleEnabled=True)


class GetScheduleHandler(ScheduleBaseHandler):
    """Handler class for GetSchedule requests"""

    def __call__(
        self, model_id: str, user_groups: Optional[List[str]] = None, is_admin: bool = False
    ) -> GetScheduleResponse:
        """Get current schedule configuration for a model"""
        # Validate model exists
        model_response = self._model_table.get_item(Key={"model_id": model_id})
        if "Item" not in model_response:
            raise ModelNotFoundError(f"Model {model_id} not found")

        model_item = model_response["Item"]

        # Check if user has access to this model based on groups
        if not is_admin and user_groups is not None:
            allowed_groups = model_item.get("allowedGroups", [])
            if not user_has_group_access(user_groups, allowed_groups):
                raise ModelNotFoundError(f"Model {model_id} not found")

        # Invoke Schedule Management Lambda
        payload = {"operation": "get", "modelId": model_id}

        response = self._lambda_client.invoke(
            FunctionName=os.environ.get("SCHEDULE_MANAGEMENT_FUNCTION_NAME"),
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )

        result = json.loads(response["Payload"].read())

        if response["StatusCode"] != 200 or result.get("statusCode") != 200:
            error_message = result.get("body", {}).get("message", "Unknown error")
            raise ValueError(f"Failed to get schedule: {error_message}")

        schedule_data = json.loads(result["body"])

        return GetScheduleResponse(
            modelId=model_id,
            scheduling=schedule_data.get("scheduling", {}),
            nextScheduledAction=schedule_data.get("nextScheduledAction"),
        )


class DeleteScheduleHandler(ScheduleBaseHandler):
    """Handler class for DeleteSchedule requests"""

    def __call__(
        self, model_id: str, user_groups: Optional[List[str]] = None, is_admin: bool = False
    ) -> DeleteScheduleResponse:
        """Delete a schedule for a model"""
        # Validate model exists
        model_response = self._model_table.get_item(Key={"model_id": model_id})
        if "Item" not in model_response:
            raise ModelNotFoundError(f"Model {model_id} not found")

        model_item = model_response["Item"]

        # Check if user has access to this model based on groups
        if not is_admin and user_groups is not None:
            allowed_groups = model_item.get("allowedGroups", [])
            if not user_has_group_access(user_groups, allowed_groups):
                raise ModelNotFoundError(f"Model {model_id} not found")

        model_status = model_item.get("model_status")

        allowed_statuses = ["InService", "Stopped"]
        if model_status not in allowed_statuses:
            raise InvalidStateTransitionError(
                f"Cannot edit schedule when model is in '{model_status}' state, model must be InService or Stopped."
            )

        # Invoke Schedule Management Lambda
        payload = {"operation": "delete", "modelId": model_id}

        response = self._lambda_client.invoke(
            FunctionName=os.environ.get("SCHEDULE_MANAGEMENT_FUNCTION_NAME"),
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )

        result = json.loads(response["Payload"].read())

        if response["StatusCode"] != 200 or result.get("statusCode") != 200:
            error_message = result.get("body", {}).get("message", "Unknown error")
            raise ValueError(f"Failed to delete schedule: {error_message}")

        return DeleteScheduleResponse(message="Schedule deleted successfully", modelId=model_id, scheduleEnabled=False)


class GetScheduleStatusHandler(ScheduleBaseHandler):
    """Handler class for GetScheduleStatus requests"""

    def __call__(
        self, model_id: str, user_groups: Optional[List[str]] = None, is_admin: bool = False
    ) -> GetScheduleStatusResponse:
        """Get current schedule status and next scheduled action for a model"""
        # Validate model exists
        model_response = self._model_table.get_item(Key={"model_id": model_id})
        if "Item" not in model_response:
            raise ModelNotFoundError(f"Model {model_id} not found")

        model_item = model_response["Item"]

        # Check if user has access to this model based on groups
        if not is_admin and user_groups is not None:
            allowed_groups = model_item.get("allowedGroups", [])
            if not user_has_group_access(user_groups, allowed_groups):
                raise ModelNotFoundError(f"Model {model_id} not found")
        auto_scaling_config = model_item.get("autoScalingConfig", {})
        scheduling_config = auto_scaling_config.get("scheduling", {})

        # Return schedule status information using boolean flags
        schedule_configured = scheduling_config.get("scheduleConfigured", False)
        last_schedule_failed = scheduling_config.get("lastScheduleFailed", False)

        # Derive status text for backward compatibility
        if not schedule_configured:
            status_text = "DISABLED"
        elif last_schedule_failed:
            status_text = "FAILED"
        else:
            status_text = "ACTIVE"

        return GetScheduleStatusResponse(
            modelId=model_id,
            scheduleEnabled=scheduling_config.get("scheduleEnabled", False),
            scheduleConfigured=schedule_configured,
            lastScheduleFailed=last_schedule_failed,
            scheduleStatus=status_text,
            scheduleType=scheduling_config.get("scheduleType", "NONE"),
            timezone=scheduling_config.get("timezone", "UTC"),
            nextScheduledAction=scheduling_config.get("nextScheduledAction"),
            lastScheduleUpdate=scheduling_config.get("lastScheduleUpdate"),
            lastScheduleFailure=scheduling_config.get("lastScheduleFailure"),
        )
