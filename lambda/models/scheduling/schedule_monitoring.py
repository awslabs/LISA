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
from datetime import datetime
from datetime import timezone as dt_timezone
from typing import Any, Dict, Optional

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from models.domain_objects import ModelStatus

logger = logging.getLogger(__name__)

# AWS clients with retry configuration
retry_config = Config(
    region_name=os.environ.get("AWS_REGION", "us-east-1"), retries={"max_attempts": 3, "mode": "adaptive"}
)
autoscaling_client = boto3.client("autoscaling", config=retry_config)
ecs_client = boto3.client("ecs", config=retry_config)
dynamodb = boto3.resource("dynamodb", config=retry_config)
model_table = dynamodb.Table(os.environ.get("MODEL_TABLE_NAME", "LISAModels"))

# Retry configuration for failed scaling operations
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_BASE = 60


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler for CloudWatch Events from Auto Scaling Groups"""
    try:
        logger.info(f"Processing CloudWatch event: {json.dumps(event, default=str)}")

        # Handle different event sources
        if "source" in event and event["source"] == "aws.autoscaling":
            return handle_autoscaling_event(event)
        else:
            # Direct invocation for testing or manual operations
            operation = event.get("operation")
            if operation == "sync_status":
                return sync_model_status(event)
            elif operation == "retry_failed":
                return retry_failed_scaling(event)
            else:
                logger.warning(f"Unknown event format: {event}")
                return {"statusCode": 200, "message": "Event processed (no action taken)"}

    except Exception as e:
        logger.error(f"Schedule monitoring error: {str(e)}", exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"error": "ScheduleMonitoringError", "message": str(e)})}


def handle_autoscaling_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Auto Scaling Group CloudWatch events"""
    try:
        detail = event.get("detail", {})
        event_type = detail.get("StatusCode")
        auto_scaling_group = detail.get("AutoScalingGroupName", "")

        logger.info(f"Processing Auto Scaling event: {event_type} for ASG: {auto_scaling_group}")

        # Find model ID by looking up which model uses this ASG
        model_id = find_model_by_asg_name(auto_scaling_group)
        if not model_id:
            logger.warning(f"Could not find model for ASG: {auto_scaling_group}")
            return {"statusCode": 200, "message": "ASG not related to LISA models"}

        # Handle different event types
        if event_type == "Successful":
            return handle_successful_scaling(model_id, auto_scaling_group, detail)
        elif event_type == "Failed":
            return handle_failed_scaling(model_id, auto_scaling_group, detail)
        else:
            logger.info(f"Ignoring Auto Scaling event type: {event_type}")
            return {"statusCode": 200, "message": f"Event type {event_type} ignored"}

    except Exception as e:
        logger.error(f"Failed to handle Auto Scaling event: {str(e)}")
        raise ValueError(f"Failed to handle Auto Scaling event: {str(e)}")


def handle_successful_scaling(model_id: str, auto_scaling_group: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """Handle successful Auto Scaling actions"""
    try:
        # Get current ECS service state to determine model status
        ecs_service_arn = get_ecs_service_name(model_id)
        if not ecs_service_arn:
            logger.warning(f"Could not find ECS service for model {model_id}")
            return {"statusCode": 200, "message": "ECS service not found"}

        # Check ECS service running count (ECS API accepts ARNs)
        running_count = get_ecs_service_running_count(ecs_service_arn)

        # Determine new model status based on running count
        if running_count == 0:
            new_status = ModelStatus.STOPPED
        elif running_count > 0:
            new_status = ModelStatus.IN_SERVICE
        else:
            logger.warning(f"Unexpected running count {running_count} for model {model_id}")
            return {"statusCode": 200, "message": "Unexpected ECS service state"}

        # Update model status in DynamoDB
        update_model_status(model_id, new_status, "Auto Scaling action completed successfully")

        logger.info(f"Successfully updated model {model_id} status to {new_status}")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Scaling event processed successfully",
                    "modelId": model_id,
                    "newStatus": new_status,
                    "runningCount": running_count,
                }
            ),
        }

    except Exception as e:
        logger.error(f"Failed to handle successful scaling for model {model_id}: {str(e)}")
        raise


def handle_failed_scaling(model_id: str, auto_scaling_group: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """Handle failed Auto Scaling actions with retry logic"""
    try:
        error_message = detail.get("StatusMessage", "Unknown scaling failure")
        logger.error(f"Auto Scaling action failed for model {model_id}: {error_message}")

        # Get current retry count for this model
        retry_count = get_current_retry_count(model_id)

        if retry_count < MAX_RETRY_ATTEMPTS:
            # Attempt retry with exponential backoff
            delay_seconds = RETRY_DELAY_BASE * (2**retry_count)
            logger.info(f"Scheduling retry {retry_count + 1} for model {model_id} in {delay_seconds} seconds")

            # Update failure tracking in DynamoDB
            update_schedule_failure(model_id, error_message, retry_count + 1)

            # Log the retry attempt
            schedule_retry(model_id, auto_scaling_group, delay_seconds, retry_count + 1)

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Scaling failure detected, retry scheduled",
                        "modelId": model_id,
                        "retryCount": retry_count + 1,
                        "delaySeconds": delay_seconds,
                    }
                ),
            }
        else:
            # Max retries exceeded, mark as failed
            logger.error(f"Max retries exceeded for model {model_id}, marking schedule as failed")

            update_schedule_status(model_id, True, error_message)

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "message": "Max retries exceeded, schedule marked as failed",
                        "modelId": model_id,
                        "finalError": error_message,
                    }
                ),
            }

    except Exception as e:
        logger.error(f"Failed to handle scaling failure for model {model_id}: {str(e)}")
        raise


def sync_model_status(event: Dict[str, Any]) -> Dict[str, Any]:
    """Manually sync model status with ECS service state"""
    model_id = event.get("modelId")
    if not model_id:
        raise ValueError("modelId is required for sync_status operation")

    try:
        # Get ECS service state
        ecs_service_arn = get_ecs_service_name(model_id)
        if not ecs_service_arn:
            raise ValueError(f"ECS service not found for model {model_id}")

        running_count = get_ecs_service_running_count(ecs_service_arn)

        # Determine correct status
        if running_count == 0:
            new_status = ModelStatus.STOPPED
        elif running_count > 0:
            new_status = ModelStatus.IN_SERVICE
        else:
            raise ValueError(f"Invalid running count: {running_count}")

        # Update model status
        update_model_status(model_id, new_status, "Manual status synchronization")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Status synchronized successfully",
                    "modelId": model_id,
                    "newStatus": new_status,
                    "runningCount": running_count,
                }
            ),
        }

    except Exception as e:
        logger.error(f"Failed to sync status for model {model_id}: {str(e)}")
        raise ValueError(f"Failed to sync status: {str(e)}")


def retry_failed_scaling(event: Dict[str, Any]) -> Dict[str, Any]:
    """Reset retry count for a failed scaling operation (manual intervention)"""
    model_id = event.get("modelId")
    if not model_id:
        raise ValueError("modelId is required for retry_failed operation")

    try:
        # Get model information to verify it exists
        model_info = get_model_info(model_id)
        if not model_info:
            raise ValueError(f"Model {model_id} not found")

        logger.info(f"Manually resetting retry count for model {model_id}")

        # Reset retry count - this allows the normal scheduling process to retry
        reset_retry_count(model_id)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {"message": "Retry count reset - normal scheduling will retry the operation", "modelId": model_id}
            ),
        }

    except Exception as e:
        logger.error(f"Failed to reset retry count for model {model_id}: {str(e)}")
        raise ValueError(f"Failed to reset retry count: {str(e)}")


def find_model_by_asg_name(asg_name: str) -> Optional[str]:
    """Find model ID by looking up which model uses the given Auto Scaling Group"""
    try:
        response = model_table.scan(
            FilterExpression="autoScalingGroup = :asg_name",
            ExpressionAttributeValues={":asg_name": asg_name},
            ProjectionExpression="model_id",
        )

        if response["Items"]:
            return response["Items"][0]["model_id"]

        return None

    except Exception as e:
        logger.error(f"Failed to find model for ASG {asg_name}: {e}")
        return None


def get_ecs_service_name(model_id: str) -> Optional[str]:
    """Get ECS service ARN for a model"""
    try:
        response = model_table.get_item(Key={"model_id": model_id})

        if "Item" not in response:
            return None

        model_item = response["Item"]

        # Check common field names for ECS service
        return model_item.get("ecs_service_arn")

    except Exception as e:
        logger.error(f"Failed to get ECS service ARN for model {model_id}: {e}")
        return None


def get_ecs_service_running_count(service_arn: str) -> int:
    """Get the running task count for an ECS service"""
    try:
        cluster_name = os.environ.get("ECS_CLUSTER_NAME")

        response = ecs_client.describe_services(cluster=cluster_name, services=[service_arn])

        if not response["services"]:
            logger.warning(f"ECS service {service_arn} not found")
            return 0

        service = response["services"][0]
        return service.get("runningCount", 0)

    except ClientError as e:
        logger.error(f"Failed to get ECS service running count for {service_arn}: {e}")
        return 0
    except Exception as e:
        logger.error(f"Unexpected error getting ECS service running count: {e}")
        return 0


def update_model_status(model_id: str, new_status: ModelStatus, reason: str) -> None:
    """Update model status in DynamoDB"""
    try:
        model_table.update_item(
            Key={"model_id": model_id},
            UpdateExpression="SET #status = :status, lastStatusUpdate = :timestamp, statusReason = :reason",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": new_status,
                ":timestamp": datetime.now(dt_timezone.utc).isoformat(),
                ":reason": reason,
            },
        )

        logger.info(f"Updated model {model_id} status to {new_status}: {reason}")

    except Exception as e:
        logger.error(f"Failed to update model status for {model_id}: {e}")
        raise


def get_current_retry_count(model_id: str) -> int:
    """Get current retry count for a model's schedule failures"""
    try:
        response = model_table.get_item(Key={"model_id": model_id})

        if "Item" not in response:
            return 0

        model_item = response["Item"]
        auto_scaling_config = model_item.get("autoScalingConfig", {})
        scheduling_config = auto_scaling_config.get("scheduling", {})
        last_failure = scheduling_config.get("lastScheduleFailure", {})

        return last_failure.get("retryCount", 0)

    except Exception as e:
        logger.error(f"Failed to get retry count for model {model_id}: {e}")
        return 0


def update_schedule_failure(model_id: str, error_message: str, retry_count: int) -> None:
    """Update schedule failure information in DynamoDB"""
    try:
        failure_info = {
            "timestamp": datetime.now(dt_timezone.utc).isoformat(),
            "error": error_message,
            "retryCount": retry_count,
        }

        model_table.update_item(
            Key={"model_id": model_id},
            UpdateExpression="SET autoScalingConfig.scheduling.lastScheduleFailure = :failure",
            ExpressionAttributeValues={":failure": failure_info},
        )

        logger.info(f"Updated schedule failure info for model {model_id}: retry {retry_count}")

    except Exception as e:
        logger.error(f"Failed to update schedule failure for model {model_id}: {e}")
        raise


def update_schedule_status(model_id: str, failed: bool, error_message: Optional[str] = None) -> None:
    """Update schedule status in DynamoDB using boolean flags"""
    try:
        update_expression = "SET autoScalingConfig.scheduling.lastScheduleFailed = :failed"
        expression_values = {":failed": failed}

        if error_message and failed:
            update_expression += ", autoScalingConfig.scheduling.lastScheduleFailure = :failure"
            expression_values[":failure"] = {
                "timestamp": datetime.now(dt_timezone.utc).isoformat(),
                "error": error_message,
                "retryCount": get_current_retry_count(model_id),
            }
        elif not failed:
            # Clear failure info on success
            update_expression += " REMOVE autoScalingConfig.scheduling.lastScheduleFailure"

        model_table.update_item(
            Key={"model_id": model_id}, UpdateExpression=update_expression, ExpressionAttributeValues=expression_values
        )

        status_text = "failed" if failed else "successful"
        logger.info(f"Updated schedule status for model {model_id} to {status_text}")

    except Exception as e:
        logger.error(f"Failed to update schedule status for model {model_id}: {e}")
        raise


def schedule_retry(model_id: str, auto_scaling_group: str, delay_seconds: int, retry_count: int) -> None:
    """Schedule a retry for a failed scaling operation"""
    logger.info(
        f"Retry scheduled for model {model_id}: "
        f"ASG={auto_scaling_group}, delay={delay_seconds}s, attempt={retry_count}"
    )


def reset_retry_count(model_id: str) -> None:
    """Reset retry count after successful operation"""
    try:
        model_table.update_item(
            Key={"model_id": model_id}, UpdateExpression="REMOVE autoScalingConfig.scheduling.lastScheduleFailure"
        )

        logger.info(f"Reset retry count for model {model_id}")

    except Exception as e:
        logger.error(f"Failed to reset retry count for model {model_id}: {e}")


def get_model_info(model_id: str) -> Optional[Dict[str, Any]]:
    """Get model information from DynamoDB"""
    try:
        response = model_table.get_item(Key={"model_id": model_id})

        if "Item" not in response:
            return None

        return response["Item"]

    except Exception as e:
        logger.error(f"Failed to get model info for {model_id}: {e}")
        return None
