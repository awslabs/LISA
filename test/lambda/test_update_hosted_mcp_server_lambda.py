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

# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Unit tests for update_hosted_mcp_server API handler."""

import functools
import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.config import Config
from moto import mock_aws

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials and env
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["MCP_SERVERS_TABLE_NAME"] = "mcp-servers-table"
os.environ["MCP_SERVERS_BY_OWNER_INDEX_NAME"] = "mcp-servers-by-owner-index"

retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")


def mock_api_wrapper(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            if isinstance(result, dict) and "statusCode" in result:
                return result
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps(result, default=str),
            }
        except Exception as e:
            return {
                "statusCode": 500,
                "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                "body": json.dumps({"error": str(e)}),
            }

    return wrapper


# Patches for utilities
patch("utilities.auth.get_username", lambda event: event["requestContext"]["authorizer"]["claims"]["username"]).start()
mock_is_admin = MagicMock(return_value=False)
patch("utilities.auth.is_admin", mock_is_admin).start()
patch("utilities.common_functions.retry_config", retry_config).start()
patch("utilities.common_functions.api_wrapper", mock_api_wrapper).start()


@pytest.fixture(scope="function")
def dynamodb():
    """Create a mock DynamoDB service."""
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture(scope="function")
def mcp_servers_table(dynamodb):
    """Create a mock DynamoDB table for MCP servers."""
    table = dynamodb.create_table(
        TableName="mcp-servers-table",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "owner", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "mcp-servers-by-owner-index",
                "KeySchema": [{"AttributeName": "owner", "KeyType": "HASH"}],
                "Projection": {"ProjectionType": "ALL"},
                "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
            }
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return table


@pytest.fixture
def lambda_context():
    return SimpleNamespace(
        function_name="test_function",
        function_version="$LATEST",
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test_function",
        memory_limit_in_mb=128,
        aws_request_id="test-request-id",
        log_group_name="/aws/lambda/test_function",
        log_stream_name="2024/03/27/[$LATEST]test123",
    )


def test_update_hosted_mcp_server_enable_success(mcp_servers_table, lambda_context):
    # Seed server as Stopped with stack
    server_item = {
        "id": "hosted-server-id",
        "name": "Test Hosted MCP Server",
        "owner": "admin-user",
        "status": "Stopped",
        "stack_name": "test-stack",
        "autoScalingConfig": {"minCapacity": 1, "maxCapacity": 2},
    }
    mcp_servers_table.put_item(Item=server_item)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "hosted-server-id"},
        "body": json.dumps({"enabled": True}),
    }

    with patch.dict(os.environ, {"UPDATE_MCP_SERVER_SFN_ARN": "arn:aws:states:us-east-1:123:stateMachine:Update"}):
        import mcp_server.lambda_functions as mcp_module

        mock_sfn_client = MagicMock()
        original_stepfunctions = mcp_module.stepfunctions
        mcp_module.stepfunctions = mock_sfn_client
        try:
            mock_is_admin.return_value = True
            with patch("mcp_server.lambda_functions.is_admin", return_value=True):
                response = mcp_module.update_hosted_mcp_server(event, lambda_context)
            assert response["statusCode"] == 200
            body = json.loads(response["body"])
            assert body["id"] == "hosted-server-id"

            mock_sfn_client.start_execution.assert_called_once()
            call_args = mock_sfn_client.start_execution.call_args
            payload = json.loads(call_args[1]["input"])
            assert payload["server_id"] == "hosted-server-id"
            assert payload["update_payload"]["enabled"] is True
        finally:
            mcp_module.stepfunctions = original_stepfunctions
            mock_is_admin.return_value = False


def test_update_hosted_mcp_server_autoscaling_mutually_exclusive(mcp_servers_table, lambda_context):
    server_item = {
        "id": "hosted-server-id",
        "name": "Test Hosted MCP Server",
        "owner": "admin-user",
        "status": "Stopped",
        "stack_name": "test-stack",
        "autoScalingConfig": {"minCapacity": 1, "maxCapacity": 2},
    }
    mcp_servers_table.put_item(Item=server_item)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "hosted-server-id"},
        "body": json.dumps({"enabled": True, "autoScalingConfig": {"minCapacity": 2}}),
    }

    import mcp_server.lambda_functions as mcp_module

    mock_is_admin.return_value = True

    with patch("mcp_server.lambda_functions.is_admin", return_value=True):
        response = mcp_module.update_hosted_mcp_server(event, lambda_context)
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "must happen in separate requests" in body["error"]
    mock_is_admin.return_value = False


def test_update_hosted_mcp_server_autoscaling_requires_stack(mcp_servers_table, lambda_context):
    server_item = {
        "id": "hosted-server-id",
        "name": "Test Hosted MCP Server",
        "owner": "admin-user",
        "status": "InService",
        # no stack_name
    }
    mcp_servers_table.put_item(Item=server_item)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "hosted-server-id"},
        "body": json.dumps({"autoScalingConfig": {"minCapacity": 2}}),
    }

    import mcp_server.lambda_functions as mcp_module

    mock_is_admin.return_value = True

    with patch("mcp_server.lambda_functions.is_admin", return_value=True):
        response = mcp_module.update_hosted_mcp_server(event, lambda_context)
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "does not have a CloudFormation stack" in body["error"]
    mock_is_admin.return_value = False


def test_update_hosted_mcp_server_not_admin(mcp_servers_table, lambda_context):
    server_item = {
        "id": "hosted-server-id",
        "name": "Test Hosted MCP Server",
        "owner": "admin-user",
        "status": "Stopped",
        "stack_name": "test-stack",
        "autoScalingConfig": {"minCapacity": 1, "maxCapacity": 2},
    }
    mcp_servers_table.put_item(Item=server_item)

    event = {
        "requestContext": {"authorizer": {"claims": {"username": "test-user"}}},
        "pathParameters": {"serverId": "hosted-server-id"},
        "body": json.dumps({"enabled": True}),
    }

    import mcp_server.lambda_functions as mcp_module

    mock_is_admin.return_value = False
    response = mcp_module.update_hosted_mcp_server(event, lambda_context)
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "Not authorized" in body["error"]


def test_update_hosted_mcp_server_not_found(mcp_servers_table, lambda_context):
    event = {
        "requestContext": {"authorizer": {"claims": {"username": "admin-user"}}},
        "pathParameters": {"serverId": "missing"},
        "body": json.dumps({"enabled": True}),
    }

    import mcp_server.lambda_functions as mcp_module

    mock_is_admin.return_value = True
    with patch("mcp_server.lambda_functions.is_admin", return_value=True):
        response = mcp_module.update_hosted_mcp_server(event, lambda_context)
    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert "not found" in body["error"].lower()
    mock_is_admin.return_value = False
