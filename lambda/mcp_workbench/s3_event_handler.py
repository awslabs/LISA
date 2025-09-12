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

"""Lambda to handle S3 events and trigger MCP Workbench rescan."""

import json
import logging
import os
from typing import Any, Dict
import urllib3
import boto3
from botocore.exceptions import ClientError
from utilities.common_functions import retry_config

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize clients
secrets_manager = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)

# Initialize HTTP client
http = urllib3.PoolManager()


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle S3 events from EventBridge and trigger MCP Workbench rescan.
    
    This function is triggered by EventBridge when S3 objects are created or deleted
    in the MCP Workbench bucket. It calls the rescan endpoint with proper authentication.
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
        
        # Get the management key for authentication
        management_key = get_management_key()
        
        # Get the API endpoint
        api_endpoint = get_api_endpoint()
        
        # Call the rescan endpoint
        rescan_response = call_rescan_endpoint(api_endpoint, management_key)
        
        logger.info(f"Rescan endpoint called successfully. Response status: {rescan_response.status}")
        
        return {
            "statusCode": 200, 
            "body": json.dumps({
                "message": "Rescan triggered successfully",
                "bucket": bucket_name,
                "event": event_name,
                "rescan_status": rescan_response.status
            })
        }
        
    except Exception as e:
        logger.error(f"Error processing S3 event: {str(e)}")
        return {"statusCode": 500, "body": json.dumps(f"Error: {str(e)}")}


def get_management_key() -> str:
    """
    Retrieve the management key from Secrets Manager.
    """
    try:
        # Get the secret name from SSM parameter
        deployment_prefix = os.environ.get("DEPLOYMENT_PREFIX")
        if not deployment_prefix:
            raise ValueError("DEPLOYMENT_PREFIX environment variable not set")
        
        secret_name_param = f"{deployment_prefix}/managementKeySecretName"
        
        response = ssm_client.get_parameter(Name=secret_name_param)
        secret_name = response["Parameter"]["Value"]
        
        logger.info(f"Retrieved secret name from SSM: {secret_name}")
        
        # Get the actual secret value
        secret_response = secrets_manager.get_secret_value(SecretId=secret_name)
        return secret_response["SecretString"]
        
    except ClientError as e:
        logger.error(f"Error retrieving management key: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error retrieving management key: {e}")
        raise


def get_api_endpoint() -> str:
    """
    Get the API endpoint URL from environment or SSM parameter.
    """
    try:
        # First try environment variable
        endpoint = os.environ.get("API_ENDPOINT")
        if endpoint:
            return endpoint
        
        # Fall back to SSM parameter
        deployment_prefix = os.environ.get("DEPLOYMENT_PREFIX")
        if not deployment_prefix:
            raise ValueError("DEPLOYMENT_PREFIX environment variable not set")
        
        endpoint_param = f"{deployment_prefix}/serve/endpoint"
        response = ssm_client.get_parameter(Name=endpoint_param)
        endpoint = response["Parameter"]["Value"]
        
        logger.info(f"Retrieved API endpoint from SSM: {endpoint}")
        return endpoint
        
    except ClientError as e:
        logger.error(f"Error retrieving API endpoint: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error retrieving API endpoint: {e}")
        raise


def call_rescan_endpoint(api_endpoint: str, management_key: str) -> urllib3.HTTPResponse:
    """
    Call the MCP Workbench rescan endpoint with proper authentication.
    """
    try:
        # Construct the rescan URL
        rescan_url = f"{api_endpoint.rstrip('/')}/v2/mcp/rescan"
        
        logger.info(f"Calling rescan endpoint: {rescan_url}")
        
        # Prepare headers
        headers = {
            'Authorization': management_key,
            'Accept': 'text/event-stream',
            'Content-Type': 'application/json'
        }
        
        # Make the HTTP GET request
        response = http.request(
            'GET',
            rescan_url,
            headers=headers,
            timeout=30.0,  # 30 second timeout
            retries=urllib3.Retry(
                total=2,
                backoff_factor=1,
                status_forcelist=[500, 502, 503, 504]
            )
        )
        
        if response.status >= 400:
            logger.warning(f"Rescan endpoint returned status {response.status}: {response.data.decode('utf-8', errors='ignore')}")
        else:
            logger.info(f"Rescan endpoint called successfully with status {response.status}")
        
        return response
        
    except Exception as e:
        logger.error(f"Error calling rescan endpoint: {e}")
        raise


def validate_s3_event(event: Dict[str, Any]) -> bool:
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
