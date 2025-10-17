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

"""Lambda handlers for DeleteModel state machine."""

import logging
import os
from copy import deepcopy
from datetime import datetime, UTC
from typing import Any, Dict
from uuid import uuid4

import boto3
from models.clients.litellm_client import LiteLLMClient
from utilities.common_functions import get_cert_path, get_rest_api_container_endpoint, retry_config

from ..domain_objects import ModelStatus

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Clients
cloudformation = boto3.client("cloudformation", region_name=os.environ["AWS_REGION"], config=retry_config)
dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
ddb_table = dynamodb.Table(os.environ["MODEL_TABLE_NAME"])
guardrails_table = dynamodb.Table(os.environ["GUARDRAILS_TABLE_NAME"])
iam_client = boto3.client("iam", region_name=os.environ["AWS_REGION"], config=retry_config)

secrets_manager = boto3.client("secretsmanager", region_name=os.environ["AWS_REGION"], config=retry_config)
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

# DDB and Payload fields
CFN_STACK_ARN = "cloudformation_stack_arn"
LITELLM_ID = "litellm_id"


def handle_set_model_to_deleting(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Start deletion workflow based on user-specified model input."""
    output_dict = deepcopy(event)
    model_id = event["modelId"]
    logger.info(f"Starting deletion workflow for model: {model_id}")
    model_key = {"model_id": model_id}
    item = ddb_table.get_item(
        Key=model_key,
        ConsistentRead=True,
        ReturnConsumedCapacity="NONE",
    ).get("Item", None)
    if not item:
        raise RuntimeError(f"Requested model '{model_id}' was not found in DynamoDB table.")
    output_dict[CFN_STACK_ARN] = item.get(CFN_STACK_ARN, None)
    output_dict[LITELLM_ID] = item.get(LITELLM_ID, None)

    ddb_table.update_item(
        Key=model_key,
        UpdateExpression="SET last_modified_date = :lmd, model_status = :ms",
        ExpressionAttributeValues={
            ":lmd": int(datetime.now(UTC).timestamp()),
            ":ms": ModelStatus.DELETING,
        },
    )
    return output_dict


def handle_delete_from_litellm(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Delete model reference from LiteLLM."""
    if event[LITELLM_ID]:  # if non-null ID
        litellm_client.delete_model(identifier=event[LITELLM_ID])
    return event


def handle_delete_guardrails(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Delete all guardrails associated with the model from both LiteLLM and DynamoDB."""
    logger.info(f"Deleting guardrails for model: {event.get('modelId')}")
    output_dict = deepcopy(event)
    
    model_id = event["modelId"]
    deleted_guardrails = []
    
    try:
        # Get all guardrails for this model from DynamoDB
        response = guardrails_table.query(
            IndexName="ModelIdIndex",
            KeyConditionExpression="model_id = :model_id",
            ExpressionAttributeValues={":model_id": model_id}
        )
        
        guardrails_to_delete = response.get("Items", [])
        
        if not guardrails_to_delete:
            logger.info(f"No guardrails found for model: {model_id}")
            output_dict["deleted_guardrails"] = []
            return output_dict
        
        logger.info(f"Found {len(guardrails_to_delete)} guardrails to delete for model: {model_id}")
        
        # Delete each guardrail from both LiteLLM and DynamoDB
        for guardrail in guardrails_to_delete:
            guardrail_id = guardrail["guardrail_id"]
            guardrail_name = guardrail["guardrail_name"]
            
            try:
                logger.info(f"Deleting guardrail from LiteLLM: {guardrail_name} (ID: {guardrail_id})")
                # Delete from LiteLLM
                litellm_client.delete_guardrail(guardrail_id)
                
                logger.info(f"Deleting guardrail from DynamoDB: {guardrail_name} (ID: {guardrail_id})")
                # Delete from DynamoDB
                guardrails_table.delete_item(
                    Key={
                        "guardrail_id": guardrail_id,
                        "model_id": model_id
                    }
                )
                
                deleted_guardrails.append({
                    "guardrail_id": guardrail_id,
                    "guardrail_name": guardrail_name,
                    "action": "deleted"
                })
                
                logger.info(f"Successfully deleted guardrail: {guardrail_name}")
                
            except Exception as delete_error:
                logger.error(f"Error deleting individual guardrail {guardrail_name}: {str(delete_error)}")
                # Continue with other guardrails even if one fails
                # We don't want to stop the entire model deletion process because of a guardrail deletion failure
                continue
                
    except Exception as e:
        logger.error(f"Error during guardrail deletion process for model {model_id}: {str(e)}")
        # Don't raise the exception - we want to continue with model deletion even if guardrail cleanup fails
        # Log the error but proceed with the deletion workflow
    
    output_dict["deleted_guardrails"] = deleted_guardrails
    logger.info(f"Completed guardrail deletion for model: {model_id}. Deleted {len(deleted_guardrails)} guardrails.")
    
    return output_dict


def handle_delete_stack(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Initialize stack deletion."""
    stack_arn = event[CFN_STACK_ARN]
    logger.info(f"Deleting CloudFormation stack: {stack_arn}")
    client_request_token = str(uuid4())
    cloudformation.delete_stack(
        StackName=stack_arn,
        ClientRequestToken=client_request_token,
    )
    return event  # no payload mutations needed between this and next state


def handle_monitor_delete_stack(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Get stack status while it is being deleted and evaluate if state machine should continue polling."""
    output_dict = deepcopy(event)
    stack_arn = event[CFN_STACK_ARN]
    stack_metadata = cloudformation.describe_stacks(StackName=stack_arn)["Stacks"][0]
    stack_status = stack_metadata["StackStatus"]
    continue_polling = True  # stack not done yet, so continue monitoring
    if stack_status == "DELETE_COMPLETE":
        continue_polling = False  # stack finished, allow state machine to stop polling
    elif stack_status.endswith("COMPLETE") or stack_status.endswith("FAILED"):
        # Didn't expect anything else, so raise error to fail state machine
        raise RuntimeError(f"Stack entered unexpected terminal state '{stack_status}'.")
    output_dict["continue_polling"] = continue_polling

    return output_dict


def handle_delete_from_ddb(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Delete item from DDB after successful deletion workflow."""
    model_key = {"model_id": event["modelId"]}
    ddb_table.delete_item(Key=model_key)
    return event
