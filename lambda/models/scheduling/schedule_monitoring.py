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
from models.clients.litellm_client import LiteLLMClient
from models.domain_objects import ModelStatus
from utilities.common_functions import get_cert_path, get_rest_api_container_endpoint

logger = logging.getLogger(__name__)

# AWS clients with retry configuration
retry_config = Config(
    region_name=os.environ.get("AWS_REGION", "us-east-1"), retries={"max_attempts": 3, "mode": "adaptive"}
)
autoscaling_client = boto3.client("autoscaling", config=retry_config)
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
    """Handle successful Auto Scaling actions using ASG state"""
    try:
        logger.info(f"Processing successful scaling for model {model_id}, ASG: {auto_scaling_group}")
        # Check ASG state directly since we already have the ASG name from the event
        try:
            response = autoscaling_client.describe_auto_scaling_groups(AutoScalingGroupNames=[auto_scaling_group])

            if not response["AutoScalingGroups"]:
                logger.error(f"ASG {auto_scaling_group} not found")
                return {"statusCode": 200, "message": "ASG not found"}

            asg = response["AutoScalingGroups"][0]
            instances = asg.get("Instances", [])
            in_service_count = len([i for i in instances if i.get("LifecycleState") == "InService"])
            total_count = len(instances)
            desired_capacity = asg.get("DesiredCapacity", 0)

            logger.info(f"ASG state: total={total_count}, in_service={in_service_count}, desired={desired_capacity}")

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

        if new_status == ModelStatus.IN_SERVICE:
            # Model scaled up, register with LiteLLM
            register_litellm(model_id)
        elif new_status == ModelStatus.STOPPED:
            # Model scaled down, de-register with LiteLLM
            remove_litellm(model_id)

        logger.info(f"Successfully updated model {model_id} status to {new_status}")

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
    """Manually sync model status using ASG state"""
    model_id = event.get("modelId")
    if not model_id:
        raise ValueError("modelId is required for sync_status operation")

    try:
        logger.info(f"Syncing status for model {model_id}")

        # Get model info
        model_info = get_model_info(model_id)
        if not model_info:
            raise ValueError(f"Model {model_id} not found")

        # Get ASG name from model record
        asg_name = model_info.get("auto_scaling_group") or model_info.get("autoScalingGroup")

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
        model_table.update_item(
            Key={"model_id": model_id},
            UpdateExpression="SET model_status = :status, lastStatusUpdate = :timestamp, statusReason = :reason",
            ExpressionAttributeValues={
                ":status": new_status,
                ":timestamp": datetime.now(dt_timezone.utc).isoformat(),
                ":reason": reason,
            },
        )

        logger.info(f"Updated model {model_id} model_status to {new_status}: {reason}")

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


def register_litellm(model_id: str) -> None:
    """Register model with LiteLLM if missing (mimics update_model.py handle_finish_update)"""
    try:
        model_key = {"model_id": model_id}
        ddb_item = model_table.get_item(Key=model_key, ConsistentRead=True).get("Item")

        if not ddb_item:
            logger.warning(f"Model {model_id} not found in DynamoDB")
            return

        # Check if already registered
        if ddb_item.get("litellm_id"):
            logger.info(f"Model {model_id} already has litellm_id: {ddb_item['litellm_id']}")
            return

        model_url = ddb_item.get("model_url")
        if not model_url:
            logger.warning(f"Model {model_id} has no model_url, cannot register with LiteLLM")
            return

        logger.info(f"Re-registering model {model_id} with LiteLLM (ASG scaled up)")

        # Initialize LiteLLM client (exact same as update_model.py)
        secrets_manager = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)
        iam_client = boto3.client("iam", region_name=os.environ["AWS_REGION"], config=retry_config)

        litellm_client = LiteLLMClient(
            base_uri=get_rest_api_container_endpoint(),
            verify=get_cert_path(iam_client),
            headers={
                "Authorization": secrets_manager.get_secret_value(
                    SecretId=os.environ.get("MANAGEMENT_KEY_NAME"), VersionStage="AWSCURRENT"
                )["SecretString"],
                "Content-Type": "application/json",
            },
        )

        litellm_config_str = os.environ.get("LITELLM_CONFIG_OBJ", json.dumps({}))
        try:
            litellm_params = json.loads(litellm_config_str)
            litellm_params = litellm_params.get("litellm_settings", {})
        except json.JSONDecodeError:
            litellm_params = {}

        litellm_params["model"] = f"openai/{ddb_item['model_config']['modelName']}"
        litellm_params["api_base"] = model_url

        # Register with LiteLLM
        litellm_response = litellm_client.add_model(
            model_name=model_id,
            litellm_params=litellm_params,
        )

        litellm_id = litellm_response["model_info"]["id"]

        # Update DynamoDB with new litellm_id
        model_table.update_item(
            Key=model_key,
            UpdateExpression="SET litellm_id = :lid",
            ExpressionAttributeValues={":lid": litellm_id},
        )

        logger.info(f"Successfully registered {model_id} with LiteLLM ID: {litellm_id}")

    except Exception as e:
        logger.error(f"Failed to register {model_id} with LiteLLM: {e}")


def remove_litellm(model_id: str) -> None:
    """Remove model from LiteLLM if registered (mimics update_model.py disable behavior)"""
    try:
        model_key = {"model_id": model_id}
        ddb_item = model_table.get_item(Key=model_key, ConsistentRead=True).get("Item")

        if not ddb_item:
            logger.warning(f"Model {model_id} not found in DynamoDB")
            return

        litellm_id = ddb_item.get("litellm_id")
        if not litellm_id:
            logger.info(f"Model {model_id} has no litellm_id, nothing to remove from LiteLLM")
            return

        logger.info(f"Removing model {model_id} from LiteLLM (ASG scaled down)")

        try:
            # Initialize LiteLLM client
            secrets_manager = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)
            iam_client = boto3.client("iam", region_name=os.environ["AWS_REGION"], config=retry_config)

            litellm_client = LiteLLMClient(
                base_uri=get_rest_api_container_endpoint(),
                verify=get_cert_path(iam_client),
                headers={
                    "Authorization": secrets_manager.get_secret_value(
                        SecretId=os.environ.get("MANAGEMENT_KEY_NAME"), VersionStage="AWSCURRENT"
                    )["SecretString"],
                    "Content-Type": "application/json",
                },
            )

            # Remove from LiteLLM
            litellm_client.delete_model(identifier=litellm_id)

            # Clear litellm_id from DynamoDB
            model_table.update_item(
                Key=model_key,
                UpdateExpression="SET litellm_id = :li",
                ExpressionAttributeValues={":li": None},
            )

            logger.info(f"Successfully removed model {model_id} from LiteLLM and cleared ID")

        except Exception as e:
            logger.error(f"Failed to remove {model_id} from LiteLLM: {e}")

    except Exception as e:
        logger.error(f"Error in remove_from_litellm_if_registered for {model_id}: {e}")


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
