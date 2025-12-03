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
from models.exception import ModelNotFoundError

logger = logging.getLogger(__name__)

# AWS clients with retry configuration
retry_config = Config(
    region_name=os.environ.get("AWS_REGION", "us-east-1"), retries={"max_attempts": 3, "mode": "adaptive"}
)
autoscaling_client = boto3.client("autoscaling", config=retry_config)
dynamodb = boto3.resource("dynamodb", config=retry_config)
model_table = dynamodb.Table(os.environ.get("MODEL_TABLE_NAME", "LISAModels"))


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler for CloudWatch Events from Auto Scaling Groups"""
    logger.info(f"Processing event - RequestId: {context.aws_request_id}")

    try:
        # Handle different event sources
        if "source" in event and event["source"] == "aws.autoscaling":
            return handle_autoscaling_event(event)
        else:
            # Direct invocation for testing or manual operations
            operation = event.get("operation")

            if operation == "sync_status":
                return sync_model_status(event)
            else:
                logger.warning(f"Unknown operation: {operation}")
                return {"statusCode": 200, "message": "Event processed (no action taken)"}

    except Exception as e:
        logger.error(f"Schedule monitoring error: {str(e)}", exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"error": "ScheduleMonitoringError", "message": str(e)})}


def handle_autoscaling_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Handle Auto Scaling Group CloudWatch events"""
    try:
        detail = event.get("detail", {})
        event_type = event.get("detail-type", "")
        auto_scaling_group = detail.get("AutoScalingGroupName", "")

        logger.info(f"Processing {event_type} for ASG: {auto_scaling_group}")

        # Find model ID by looking up which model uses this ASG
        model_id = find_model_by_asg_name(auto_scaling_group)
        if not model_id:
            logger.warning(f"ASG {auto_scaling_group} not associated with LISA models")
            return {"statusCode": 200, "message": "ASG not related to LISA models"}

        # Handle different event types
        if event_type in ["EC2 Instance Launch Successful", "EC2 Instance Terminate Successful"]:
            return handle_successful_scaling(model_id, auto_scaling_group, detail)
        else:
            logger.info(f"Event type '{event_type}' not handled")
            return {"statusCode": 200, "message": f"Event type {event_type} ignored"}

    except Exception as e:
        logger.error(f"Failed to handle Auto Scaling event: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to handle Auto Scaling event: {str(e)}")


def handle_successful_scaling(model_id: str, auto_scaling_group: str, detail: Dict[str, Any]) -> Dict[str, Any]:
    """Handle successful Auto Scaling actions using ASG state"""
    try:
        # Check ASG state to determine model status
        try:
            response = autoscaling_client.describe_auto_scaling_groups(AutoScalingGroupNames=[auto_scaling_group])

            if not response["AutoScalingGroups"]:
                logger.error(f"ASG {auto_scaling_group} not found")
                return {"statusCode": 200, "message": "ASG not found"}

            asg = response["AutoScalingGroups"][0]
            instances = asg.get("Instances", [])
            in_service_count = len([i for i in instances if i.get("LifecycleState") == "InService"])
            desired_capacity = asg.get("DesiredCapacity", 0)

            # Determine new model status based on ASG instance state
            if in_service_count > 0:
                new_status = ModelStatus.IN_SERVICE
                reason = f"Auto Scaling completed: ASG has {in_service_count} instances in service"
            else:
                new_status = ModelStatus.STOPPED
                reason = "Auto Scaling completed: ASG has no instances in service"

        except ClientError as e:
            logger.error(f"Failed to check ASG state: {e}")
            return {"statusCode": 500, "message": f"Failed to check ASG state: {str(e)}"}

        # Update model status in DynamoDB
        update_model_status(model_id, new_status, reason)

        logger.info(f"Updated model {model_id} status to {new_status}")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Scaling event processed successfully",
                    "modelId": model_id,
                    "newStatus": new_status,
                    "asgName": auto_scaling_group,
                    "inServiceCount": in_service_count,
                    "desiredCapacity": desired_capacity,
                }
            ),
        }

    except Exception as e:
        logger.error(f"Failed to handle successful scaling for model {model_id}: {str(e)}")
        raise


def sync_model_status(event: Dict[str, Any]) -> Dict[str, Any]:
    """Manually sync model status using ASG state"""
    model_id = event.get("modelId")
    if not model_id:
        raise ValueError("modelId is required for sync_status operation")

    try:
        logger.info(f"Syncing status for model {model_id}")

        # Check if ASG name is provided directly
        asg_name = event.get("autoScalingGroup")

        if not asg_name:
            # Get model info and ASG name from model record as fallback
            model_info = get_model_info(model_id)
            if not model_info:
                raise ModelNotFoundError(f"Model {model_id} not found")

            asg_name = model_info.get("auto_scaling_group")

            if not asg_name:
                raise ValueError(f"No ASG information found for model {model_id}")

        logger.info(f"Checking ASG state: {asg_name}")

        try:
            response = autoscaling_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg_name])

            if not response["AutoScalingGroups"]:
                raise ValueError(f"ASG {asg_name} not found")

            asg = response["AutoScalingGroups"][0]
            instances = asg.get("Instances", [])
            in_service_count = len([i for i in instances if i.get("LifecycleState") == "InService"])
            total_count = len(instances)
            desired_capacity = asg.get("DesiredCapacity", 0)

            logger.info(f"ASG state: total={total_count}, in_service={in_service_count}, desired={desired_capacity}")

            if in_service_count > 0:
                new_status = ModelStatus.IN_SERVICE
                reason = f"ASG has {in_service_count} instances in service (desired: {desired_capacity})"
            else:
                new_status = ModelStatus.STOPPED
                reason = f"ASG has no instances in service (desired: {desired_capacity})"

        except ClientError as e:
            logger.error(f"Failed to check ASG state: {e}")
            raise ValueError(f"Failed to check ASG {asg_name}: {str(e)}")

        # Update model status
        update_model_status(model_id, new_status, f"Manual sync: {reason}")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Status synchronized successfully",
                    "modelId": model_id,
                    "newStatus": new_status,
                    "reason": reason,
                }
            ),
        }

    except Exception as e:
        logger.error(f"Failed to sync status for model {model_id}: {str(e)}")
        raise ValueError(f"Failed to sync status: {str(e)}")


def find_model_by_asg_name(asg_name: str) -> Optional[str]:
    """Find model ID by looking up which model uses the given Auto Scaling Group"""
    try:
        response = model_table.scan(
            FilterExpression="auto_scaling_group = :asg_name",
            ExpressionAttributeValues={":asg_name": asg_name},
            ProjectionExpression="model_id",
        )

        if response["Items"]:
            return response["Items"][0]["model_id"]

        return None

    except Exception as e:
        logger.error(f"Failed to find model for ASG {asg_name}: {e}")
        return None


def update_model_status(model_id: str, new_status: ModelStatus, reason: str) -> None:
    """Update model status in DynamoDB"""
    try:
        # Convert enum to string value for DynamoDB
        status_str = new_status.value if hasattr(new_status, "value") else str(new_status)

        model_table.update_item(
            Key={"model_id": model_id},
            UpdateExpression="SET model_status = :status, lastStatusUpdate = :timestamp, statusReason = :reason",
            ExpressionAttributeValues={
                ":status": status_str,
                ":timestamp": datetime.now(dt_timezone.utc).isoformat(),
                ":reason": reason,
            },
        )

        logger.info(f"Updated model {model_id} model_status to {status_str}: {reason}")

    except Exception as e:
        logger.error(f"Failed to update model status for {model_id}: {e}")
        raise


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
