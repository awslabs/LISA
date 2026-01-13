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

"""Lambda to handle S3 events and trigger MCP Workbench service redeployment."""

import json
import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError
from utilities.common_functions import retry_config

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize clients
ecs_client = boto3.client("ecs", region_name=os.environ["AWS_REGION"], config=retry_config)
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Handle S3 events from EventBridge and trigger MCP Workbench service redeployment.

    This function is triggered by EventBridge when S3 objects are created or deleted
    in the MCP Workbench bucket. It forces a new deployment of the MCPWORKBENCH ECS service.
    """
    logger.info(f"Received S3 event: {json.dumps(event, default=str)}")

    try:
        # Extract event details
        detail = event.get("detail", {})
        bucket_name = detail.get("bucket", {}).get("name")
        event_name = detail.get("eventName", "")

        if not bucket_name:
            logger.error("Missing bucket name in event details")
            return {"statusCode": 400, "body": json.dumps("Missing bucket name")}

        logger.info(f"Processing S3 event '{event_name}' for bucket: {bucket_name}")

        # Get ECS cluster and service names
        cluster_name = get_cluster_name()
        service_name = get_service_name()

        # Force new deployment of the MCPWORKBENCH service
        deployment_response = force_service_deployment(cluster_name, service_name)

        deployment_id = deployment_response.get("service", {}).get("deployments", [{}])[0].get("id", "unknown")
        logger.info(f"Service deployment triggered successfully. Deployment ARN: {deployment_id}")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "MCPWORKBENCH service redeployment triggered successfully",
                    "bucket": bucket_name,
                    "event": event_name,
                    "cluster": cluster_name,
                    "service": service_name,
                    "deployment_id": deployment_response.get("service", {})
                    .get("deployments", [{}])[0]
                    .get("id", "unknown"),
                }
            ),
        }

    except Exception as e:
        logger.error(f"Error processing S3 event: {str(e)}")
        return {"statusCode": 500, "body": json.dumps(f"Error: {str(e)}")}


def get_cluster_name() -> str:
    """
    Get the ECS cluster name from environment variables or construct it from deployment info.
    """
    try:
        # First try environment variable
        cluster_name = os.environ.get("ECS_CLUSTER_NAME")
        if cluster_name:
            return cluster_name

        # Fall back to constructing from deployment info
        deployment_prefix = os.environ.get("DEPLOYMENT_PREFIX")
        if not deployment_prefix:
            raise ValueError("DEPLOYMENT_PREFIX environment variable not set")

        # Get deployment name from SSM parameter
        deployment_name_param = f"{deployment_prefix}/deploymentName"
        try:
            response = ssm_client.get_parameter(Name=deployment_name_param)
            deployment_name = response["Parameter"]["Value"]
        except ClientError:
            # If parameter doesn't exist, extract from deployment prefix
            # deployment_prefix format is typically /deploymentName-stage
            deployment_name = deployment_prefix.split("/")[-1].split("-")[0]

        # Construct cluster name using the same pattern as CDK: createCdkId([config.deploymentName, identifier], 32, 2)
        # The identifier for the API cluster is typically "serve" or similar
        api_name = os.environ.get("API_NAME", "serve")
        cluster_name = f"{deployment_name}-{api_name}"

        logger.info(f"Constructed cluster name: {cluster_name}")
        return cluster_name

    except Exception as e:
        logger.error(f"Error getting cluster name: {e}")
        raise


def get_service_name() -> str:
    """
    Get the MCPWORKBENCH service name from environment variables or construct it.
    """
    try:
        # First try environment variable
        service_name = os.environ.get("MCPWORKBENCH_SERVICE_NAME")
        if service_name:
            return service_name

        # Fall back to constructing the service name
        # Based on CDK code: createCdkId([name], 32, 2) where name is ECSTasks.MCPWORKBENCH
        service_name = "MCPWORKBENCH"

        logger.info(f"Using service name: {service_name}")
        return service_name

    except Exception as e:
        logger.error(f"Error getting service name: {e}")
        raise


def force_service_deployment(cluster_name: str, service_name: str) -> dict[str, Any]:
    """
    Force a new deployment of the specified ECS service.
    """
    try:
        logger.info(f"Forcing new deployment for service '{service_name}' in cluster '{cluster_name}'")

        # Call ECS update_service with forceNewDeployment=True
        response = ecs_client.update_service(cluster=cluster_name, service=service_name, forceNewDeployment=True)

        logger.info(f"Successfully triggered new deployment for service '{service_name}'")
        return dict(response)  # Convert to dict to satisfy return type

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_message = e.response.get("Error", {}).get("Message", str(e))

        if error_code == "ServiceNotFoundException":
            logger.error(f"Service '{service_name}' not found in cluster '{cluster_name}'")
        elif error_code == "ClusterNotFoundException":
            logger.error(f"Cluster '{cluster_name}' not found")
        else:
            logger.error(f"ECS error ({error_code}): {error_message}")

        raise
    except Exception as e:
        logger.error(f"Unexpected error forcing service deployment: {e}")
        raise


def validate_s3_event(event: dict[str, Any]) -> bool:
    """
    Validate that the event is a proper S3 event from EventBridge.
    """
    try:
        source = event.get("source")
        detail_type = event.get("detail-type")
        detail = event.get("detail", {})

        # Check if it's an S3 event
        if source not in ["aws.s3", "debug"]:
            return False

        # Check if it's an object event
        if detail_type not in ["Object Created", "Object Deleted"]:
            return False

        # Check if bucket information is present
        if not detail.get("bucket", {}).get("name"):
            return False

        return True

    except Exception as e:
        logger.error(f"Error validating S3 event: {e}")
        return False
