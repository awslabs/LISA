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
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

import boto3
from botocore.config import Config

from ..scheduling import schedule_management

logger = logging.getLogger(__name__)

retry_config = Config(
    region_name=os.environ.get("AWS_REGION", "us-east-1"), retries={"max_attempts": 3, "mode": "adaptive"}
)
dynamodb = boto3.resource("dynamodb", config=retry_config)
model_table = dynamodb.Table(os.environ.get("MODEL_TABLE_NAME", "LISAModels"))


def handle_schedule_creation(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Create Auto Scaling scheduled actions for the model if scheduling is configured"""
    logger.info(f"Processing schedule creation for model: {event.get('modelId')}")
    output_dict = event.copy()

    # Only proceed if scheduling is configured
    scheduling_config = event.get("autoScalingConfig", {}).get("scheduling")
    if not scheduling_config:
        logger.info(f"No scheduling configured for model {event.get('modelId')} - model will run 24/7")
        return output_dict

    model_id = event["modelId"]
    auto_scaling_group = event.get("autoScalingGroup")

    if not auto_scaling_group:
        logger.error(f"No Auto Scaling Group found for model {model_id}")
        # Don't fail the entire model creation - just log the error
        logger.warning(
            f"Model {model_id} created successfully but scheduling failed. User can add schedule later via API."
        )
        return output_dict

    try:
        # Call schedule management function directly
        payload = {
            "operation": "update",
            "modelId": model_id,
            "scheduleConfig": scheduling_config,
            "autoScalingGroup": auto_scaling_group,
        }

        result = schedule_management.update_schedule(payload)

        if result.get("statusCode") == 200:
            result_body = json.loads(result["body"]) if isinstance(result["body"], str) else result["body"]
            scheduled_action_arns = result_body.get("scheduledActionArns", [])

            logger.info(f"Created {len(scheduled_action_arns)} scheduled actions for model {model_id}")
            output_dict["scheduled_action_arns"] = scheduled_action_arns
        else:
            error_message = result.get("body", {}).get("message", "Unknown error")
            logger.error(f"Failed to create scheduled actions for model {model_id}: {error_message}")

            # Update model with failure status but don't fail the entire model creation
            update_schedule_failure_status(model_id, error_message)

            # Log error but don't fail model creation - schedule can be added later
            logger.warning(
                f"Model {model_id} created successfully but scheduling failed. User can add schedule later via API."
            )

    except Exception as e:
        logger.error(f"Failed to create scheduled actions for model {model_id}: {str(e)}")

        # Update model with failure status but don't fail the entire model creation
        update_schedule_failure_status(model_id, str(e))

        # Log error but don't fail model creation - schedule can be added later
        logger.warning(
            f"Model {model_id} created successfully but scheduling failed. User can add schedule later via API."
        )

    return output_dict


def handle_schedule_update(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Update Auto Scaling scheduled actions when schedule configuration changes"""
    logger.info(f"Processing schedule update for model: {event.get('modelId')}")
    output_dict = event.copy()

    model_id = event["modelId"]
    new_scheduling_config = event.get("autoScalingConfig", {}).get("scheduling")
    auto_scaling_group = event.get("autoScalingGroup")

    # Check if schedule update is needed
    has_schedule_update = event.get("has_schedule_update", False)
    if not has_schedule_update:
        logger.info(f"No schedule update needed for model {model_id}")
        return output_dict

    try:
        payload = {
            "operation": "update",
            "modelId": model_id,
            "scheduleConfig": new_scheduling_config,
            "autoScalingGroup": auto_scaling_group,
        }

        result = schedule_management.update_schedule(payload)

        if result.get("statusCode") == 200:
            result_body = json.loads(result["body"]) if isinstance(result["body"], str) else result["body"]
            scheduled_action_arns = result_body.get("scheduledActionArns", [])

            logger.info(f"Updated schedule for model {model_id}: {len(scheduled_action_arns)} actions")
            output_dict["scheduled_action_arns"] = scheduled_action_arns
        else:
            error_message = result.get("body", {}).get("message", "Unknown error")
            logger.error(f"Failed to update scheduled actions for model {model_id}: {error_message}")

            # Update schedule status to failed
            update_schedule_failure_status(model_id, error_message)

            # Don't fail the model update - just log the scheduling failure
            logger.warning(f"Model {model_id} updated successfully but schedule update failed.")

    except Exception as e:
        logger.error(f"Failed to update scheduled actions for model {model_id}: {str(e)}")

        # Update schedule status to failed
        update_schedule_failure_status(model_id, str(e))

        # Don't fail the model update - just log the scheduling failure
        logger.warning(f"Model {model_id} updated successfully but schedule update failed.")

    return output_dict


def handle_cleanup_schedule(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Clean up scheduled actions before deleting the model"""
    logger.info(f"Cleaning up schedule for model: {event.get('modelId')}")
    output_dict = event.copy()

    model_id = event["modelId"]

    try:
        payload = {"operation": "delete", "modelId": model_id}

        result = schedule_management.delete_schedule(payload)

        if result.get("statusCode") == 200:
            logger.info(f"Successfully cleaned up schedule for model {model_id}")
        else:
            error_message = result.get("body", {}).get("message", "Unknown error")
            logger.warning(f"Failed to cleanup scheduled actions for model {model_id}: {error_message}")

    except Exception as e:
        logger.warning(f"Failed to cleanup scheduled actions for model {model_id}: {str(e)}")

    return output_dict


def detect_schedule_changes(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Detect if schedule configuration has changed during model update"""
    logger.info(f"Detecting schedule changes for model: {event.get('modelId')}")
    output_dict = event.copy()

    model_id = event["modelId"]
    new_auto_scaling_config = event.get("autoScalingConfig", {})
    new_scheduling_config = new_auto_scaling_config.get("scheduling")

    has_schedule_update = False

    try:
        # Get current model to compare schedules
        response = model_table.get_item(Key={"model_id": model_id})
        if "Item" in response:
            current_auto_scaling_config = response["Item"].get("autoScalingConfig", {})
            current_scheduling_config = current_auto_scaling_config.get("scheduling")

            # Compare schedules to see if update is needed
            if current_scheduling_config != new_scheduling_config:
                has_schedule_update = True
                logger.info(f"Schedule change detected for model {model_id}")

                # Store existing scheduled action ARNs for cleanup
                existing_arns = (
                    current_scheduling_config.get("scheduledActionArns", [])
                    if isinstance(current_scheduling_config, dict)
                    else []
                )
                output_dict["existing_scheduled_action_arns"] = existing_arns
        else:
            # New schedule for existing model
            if new_scheduling_config:
                has_schedule_update = True
                logger.info(f"New schedule detected for model {model_id}")

    except Exception as e:
        logger.warning(f"Could not check existing schedule for {model_id}: {e}")
        # Assume update needed if we can't check
        if new_scheduling_config:
            has_schedule_update = True

    output_dict["has_schedule_update"] = has_schedule_update

    return output_dict


def update_schedule_failure_status(model_id: str, error_message: str) -> None:
    """Update model with schedule failure status using boolean flags"""
    try:
        failure_info = {"timestamp": datetime.now(timezone.utc).isoformat(), "error": error_message, "retryCount": 0}

        model_table.update_item(
            Key={"model_id": model_id},
            UpdateExpression=(
                "SET autoScalingConfig.scheduling.lastScheduleFailed = :failed, "
                "autoScalingConfig.scheduling.lastScheduleFailure = :failure"
            ),
            ExpressionAttributeValues={":failed": True, ":failure": failure_info},
        )

        logger.info(f"Updated schedule failure status for model {model_id}")

    except Exception as e:
        logger.error(f"Failed to update schedule failure status for model {model_id}: {e}")
