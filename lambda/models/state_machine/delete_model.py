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

import os
from copy import deepcopy
from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

import boto3
from utilities.common_functions import retry_config

from ..domain_objects import ModelStatus

cloudformation = boto3.client("cloudformation", region_name=os.environ["AWS_REGION"], config=retry_config)
dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
ddb_table = dynamodb.Table(os.environ["MODEL_TABLE_NAME"])

# DDB and Payload fields
CFN_STACK_ARN = "cloudformation_stack_arn"
MODEL_ID = "model_id"


def handle_set_model_to_deleting(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Start deletion workflow based on user-specified model input."""
    output_dict = deepcopy(event)
    model_id = event[MODEL_ID]
    model_key = {MODEL_ID: model_id}
    item = ddb_table.get_item(
        Key=model_key,
        ConsistentRead=True,
        ReturnConsumedCapacity="NONE",
    ).get("Item", None)
    if not item:
        raise RuntimeError(f"Requested model '{model_id}' was not found in DynamoDB table.")
    output_dict[CFN_STACK_ARN] = item.get(CFN_STACK_ARN, None)

    ddb_table.update_item(
        Key=model_key,
        UpdateExpression="SET last_modified_date = :lmd, model_status = :ms",
        ExpressionAttributeValues={
            ":lmd": int(datetime.utcnow().timestamp()),
            ":ms": ModelStatus.DELETING,
        },
    )
    return output_dict


def handle_delete_from_litellm(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Delete model reference from LiteLLM."""
    output_dict = deepcopy(event)
    pass  # TODO: allow LiteLLM direct modifications from SFN/Lambda without direct user credentials
    return output_dict


def handle_delete_stack(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Initialize stack deletion."""
    stack_arn = event[CFN_STACK_ARN]
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
    model_key = {MODEL_ID: event[MODEL_ID]}
    ddb_table.delete_item(Key=model_key)
    return event