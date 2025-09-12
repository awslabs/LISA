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

"""Lambda to update connection secret when management key is rotated."""

import json
import logging
import os
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError
from utilities.common_functions import retry_config

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

secrets_manager = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)
events_client = boto3.client("events", region_name=os.environ["AWS_REGION"], config=retry_config)


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Handle management key rotation events and update connection secrets.
    
    This function is triggered by EventBridge when a management key is rotated.
    It updates the connection secret used by the MCP Workbench API destination.
    """
    logger.info(f"Received event: {json.dumps(event, default=str)}")
    
    try:
        # Extract event details
        detail = event.get("detail", {})
        secret_arn = detail.get("secretArn")
        secret_name = detail.get("secretName")
        new_version_id = detail.get("newVersionId")
        rotation_type = detail.get("rotationType")
        
        if not secret_arn or not new_version_id:
            logger.error("Missing required event details: secretArn or newVersionId")
            return {"statusCode": 400, "body": json.dumps("Missing required event details")}
        
        if rotation_type != "management-key":
            logger.info(f"Ignoring rotation event for type: {rotation_type}")
            return {"statusCode": 200, "body": json.dumps("Event ignored - not a management key rotation")}
        
        logger.info(f"Processing management key rotation for secret: {secret_name}")
        
        # Get the new management key value
        new_management_key = get_new_management_key(secret_arn, new_version_id)
        
        # Update connection secrets that use this management key
        update_connection_secrets(new_management_key, secret_name)
        
        logger.info("Successfully updated connection secrets")
        return {"statusCode": 200, "body": json.dumps("Connection secrets updated successfully")}
        
    except Exception as e:
        logger.error(f"Error updating connection secrets: {str(e)}")
        return {"statusCode": 500, "body": json.dumps(f"Error: {str(e)}")}


def get_new_management_key(secret_arn: str, version_id: str) -> str:
    """
    Retrieve the new management key from Secrets Manager.
    """
    try:
        response = secrets_manager.get_secret_value(
            SecretId=secret_arn,
            VersionId=version_id,
            VersionStage="AWSCURRENT"
        )
        return response["SecretString"]
    except ClientError as e:
        logger.error(f"Error retrieving new management key: {e}")
        raise


def update_connection_secrets(new_management_key: str, management_secret_name: str) -> None:
    """
    Update all connection secrets that reference the management key.
    
    This function finds EventBridge connections that use the management key
    and updates them with the new key value.
    """
    try:
        # Get the deployment prefix from environment or derive from secret name
        deployment_prefix = os.environ.get("DEPLOYMENT_PREFIX")
        if not deployment_prefix and management_secret_name:
            # Extract deployment name from secret name (format: {deployment}-lisa-management-key)
            parts = management_secret_name.split("-")
            if len(parts) >= 3 and parts[-2:] == ["lisa", "management"]:
                deployment_name = "-".join(parts[:-3])  # Everything before "-lisa-management"
                deployment_prefix = f"/lisa/{deployment_name}"
        
        if not deployment_prefix:
            logger.warning("Could not determine deployment prefix, using default pattern")
            deployment_prefix = "/lisa"
        
        logger.info(f"Updating connections for deployment prefix: {deployment_prefix}")
        
        # List all EventBridge connections to find ones that might use the management key
        # Note: list_connections doesn't support boto3 paginator, but supports manual pagination
        connections_updated = 0
        next_token = None
        
        while True:
            # Prepare the request parameters
            list_params = {'Limit': 100}  # Set a reasonable limit per page
            if next_token:
                list_params['NextToken'] = next_token
            
            response = events_client.list_connections(**list_params)
            
            # Process connections in this page
            for connection in response.get('Connections', []):
                connection_name = connection['Name']
                connection_arn = connection['ConnectionArn']
                
                # Check if this connection is related to our deployment
                # Look for connections with names containing the deployment pattern
                if should_update_connection(connection_name, deployment_prefix):
                    try:
                        update_connection_authorization(connection_name, new_management_key)
                        connections_updated += 1
                        logger.info(f"Updated connection: {connection_name}")
                    except Exception as e:
                        logger.error(f"Failed to update connection {connection_name}: {e}")
                        # Continue with other connections even if one fails
            
            # Check if there are more pages
            next_token = response.get('NextToken')
            if not next_token:
                break
            
            logger.info(f"Processing next page of connections (token: {next_token[:20]}...)")
        
        logger.info(f"Updated {connections_updated} connections")
        
    except ClientError as e:
        logger.error(f"Error updating connection secrets: {e}")
        raise


def should_update_connection(connection_name: str, deployment_prefix: str) -> bool:
    """
    Determine if a connection should be updated based on naming patterns.
    """
    # Extract deployment name from prefix (e.g., "/lisa/dev" -> "dev")
    deployment_parts = deployment_prefix.strip("/").split("/")
    deployment_name = deployment_parts[-1] if len(deployment_parts) > 1 else "lisa"
    
    # Check for common connection naming patterns
    patterns = [
        f"{deployment_name}",
        "RescanMCPWorkbench",
        "MCPWorkbench",
        "lisa",
    ]
    
    connection_lower = connection_name.lower()
    return any(pattern.lower() in connection_lower for pattern in patterns)


def update_connection_authorization(connection_name: str, new_api_key: str) -> None:
    """
    Update the authorization for an EventBridge connection with the new API key.
    """
    try:
        # Update the connection with new authorization
        events_client.update_connection(
            Name=connection_name.split('/')[-1],  # Extract connection name from ARN
            AuthorizationType='API_KEY',
            AuthParameters={
                'ApiKeyAuthParameters': {
                    'ApiKeyName': 'Authorization',
                    'ApiKeyValue': new_api_key
                }
            }
        )
        logger.info(f"Successfully updated connection authorization: {connection_name}")
        
    except ClientError as e:
        logger.error(f"Error updating connection authorization: {e}")
        raise


# Legacy function for backward compatibility
def update_connection_secret(event: dict, ctx: dict) -> None:
    """Legacy function - deprecated, use handler instead."""
    logger.warning("update_connection_secret is deprecated, use handler instead")
    return handler(event, ctx)
