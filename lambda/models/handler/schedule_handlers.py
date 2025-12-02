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
from typing import Any, List, Optional

from ..domain_objects import (
    DeleteScheduleResponse,
    GetScheduleResponse,
    GetScheduleStatusResponse,
    SchedulingConfig,
    UpdateScheduleResponse,
)
from ..scheduling import schedule_management
from .base_handler import BaseApiHandler
from .utils import get_model_and_validate_access, get_model_and_validate_status


class ScheduleBaseHandler(BaseApiHandler):
    """Base handler for schedule operations"""

    def __init__(
        self,
        autoscaling_client: Any,
        stepfunctions_client: Any,
        model_table_resource: Any,
        guardrails_table_resource: Any,
    ):
        """Initialize schedule handler"""
        super().__init__(autoscaling_client, stepfunctions_client, model_table_resource, guardrails_table_resource)


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
        # Validate model exists, user access, and model status
        model_item = get_model_and_validate_status(
            self._model_table, model_id, user_groups=user_groups, is_admin=is_admin
        )

        # Get Auto Scaling Group name from model
        auto_scaling_group = model_item.get("auto_scaling_group")
        if not auto_scaling_group:
            raise ValueError("Model does not have an Auto Scaling Group configured")

        payload = {
            "operation": "update",
            "modelId": model_id,
            "scheduleConfig": schedule_config.model_dump(),
            "autoScalingGroup": auto_scaling_group,
        }

        try:
            result = schedule_management.update_schedule(payload)
        except Exception as e:
            raise ValueError(f"Failed to create/update schedule: {str(e)}")

        result_body = json.loads(result["body"]) if isinstance(result["body"], str) else result["body"]
        schedule_enabled = result_body.get("scheduleEnabled", False)

        return UpdateScheduleResponse(
            message="Schedule updated successfully", modelId=model_id, scheduleEnabled=schedule_enabled
        )


class GetScheduleHandler(ScheduleBaseHandler):
    """Handler class for GetSchedule requests"""

    def __call__(
        self, model_id: str, user_groups: Optional[List[str]] = None, is_admin: bool = False
    ) -> GetScheduleResponse:
        """Get current schedule configuration for a model"""
        # Validate model exists and user access
        get_model_and_validate_access(self._model_table, model_id, user_groups, is_admin)

        payload = {"operation": "get", "modelId": model_id}

        try:
            result = schedule_management.get_schedule(payload)
            schedule_data = json.loads(result["body"]) if isinstance(result["body"], str) else result["body"]

            return GetScheduleResponse(
                modelId=model_id,
                scheduling=schedule_data.get("scheduling", {}),
                nextScheduledAction=schedule_data.get("nextScheduledAction"),
            )
        except Exception as e:
            raise ValueError(f"Failed to get schedule: {str(e)}")


class DeleteScheduleHandler(ScheduleBaseHandler):
    """Handler class for DeleteSchedule requests"""

    def __call__(
        self, model_id: str, user_groups: Optional[List[str]] = None, is_admin: bool = False
    ) -> DeleteScheduleResponse:
        """Delete a schedule for a model"""
        # Validate model exists, user access, and model status
        get_model_and_validate_status(self._model_table, model_id, user_groups=user_groups, is_admin=is_admin)

        # Call schedule management function directly
        payload = {"operation": "delete", "modelId": model_id}

        try:
            schedule_management.delete_schedule(payload)
        except Exception as e:
            raise ValueError(f"Failed to delete schedule: {str(e)}")

        return DeleteScheduleResponse(message="Schedule deleted successfully", modelId=model_id, scheduleEnabled=False)


class GetScheduleStatusHandler(ScheduleBaseHandler):
    """Handler class for GetScheduleStatus requests"""

    def __call__(
        self, model_id: str, user_groups: Optional[List[str]] = None, is_admin: bool = False
    ) -> GetScheduleStatusResponse:
        """Get current schedule status and next scheduled action for a model"""
        # Validate model exists and user access
        model_item = get_model_and_validate_access(self._model_table, model_id, user_groups, is_admin)

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
            scheduleType=scheduling_config.get("scheduleType"),
            timezone=scheduling_config.get("timezone", "UTC"),
            nextScheduledAction=scheduling_config.get("nextScheduledAction"),
            lastScheduleUpdate=scheduling_config.get("lastScheduleUpdate"),
            lastScheduleFailure=scheduling_config.get("lastScheduleFailure"),
        )
