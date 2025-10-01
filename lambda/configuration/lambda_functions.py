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

"""Lambda functions for managing sessions."""
import json
import logging
import os
import time
from decimal import Decimal
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError
from mcp_server.models import McpServerModel, McpServerStatus
from mcp_workbench.lambda_functions import MCPWORKBENCH_UUID
from utilities.common_functions import api_wrapper, get_property_path, retry_config

logger = logging.getLogger(__name__)

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
table = dynamodb.Table(os.environ["CONFIG_TABLE_NAME"])


@api_wrapper
def get_configuration(event: dict, context: dict) -> Dict[str, Any]:
    """List configuration entries by configScope from DynamoDB."""
    config_scope = event["queryStringParameters"]["configScope"]

    return _get_configurations(config_scope)


def _get_configurations(config_scope: str) -> dict[str, Any]:
    response = {}
    try:
        response = table.query(
            KeyConditionExpression="#s = :configScope",
            ExpressionAttributeNames={"#s": "configScope"},
            ExpressionAttributeValues={":configScope": config_scope},
            ScanIndexForward=False,
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.warning(f"No record found with session id: {config_scope}")
        else:
            logger.exception("Error fetching session")

    return response.get("Items", {})  # type: ignore [no-any-return]


@api_wrapper
def update_configuration(event: dict, context: dict) -> None:
    """Update configuration in DynamoDB."""
    # from https://stackoverflow.com/a/71446846
    body = json.loads(event["body"], parse_float=Decimal)
    body["created_at"] = str(Decimal(time.time()))

    # check if showMcpWorkbench configuration changed
    old_configurations = _get_configurations(body["configScope"])
    old_configuration = old_configurations[0] if old_configurations else {}
    check_show_mcp_workbench(body, old_configuration)

    try:
        table.put_item(Item=body)
    except ClientError:
        logger.exception("Error updating session in DynamoDB")


def check_show_mcp_workbench(body, old_configuration):
    old_show_mcp_value = get_property_path(old_configuration, "configuration.enabledComponents.showMcpWorkbench")
    new_show_mcp_value = get_property_path(body, "configuration.enabledComponents.showMcpWorkbench")

    # check if the value changed
    if old_show_mcp_value != new_show_mcp_value:
        from mcp_server.lambda_functions import table as mcp_servers_table

        if new_show_mcp_value:
            mcp_server_model = McpServerModel(
                id=MCPWORKBENCH_UUID,
                owner="lisa:public",
                name="MCP Workbench",
                description="MCP Workbench Tools",
                customHeaders={"Authorization": "Bearer {LISA_BEARER_TOKEN}"},
                url=f"{os.getenv('FASTAPI_ENDPOINT')}/v2/mcp/",
                status=McpServerStatus.ACTIVE,
            )

            # Insert the new mcp server item into the DynamoDB table
            mcp_servers_table.put_item(Item=mcp_server_model.model_dump(exclude_none=True))
        else:
            logger.info("Deleting mcp server MCP Workbench Server")
            mcp_servers_table.delete_item(Key={"id": MCPWORKBENCH_UUID, "owner": "lisa:public"})
