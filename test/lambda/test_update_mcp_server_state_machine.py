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

"""Unit tests for update_mcp_server state machine functions."""

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
os.environ["DEPLOYMENT_PREFIX"] = "/test"

# Create retry config
retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")

# Mock boto3 clients used by the module
mock_ecs = MagicMock()
mock_cfn = MagicMock()
mock_app_autoscaling = MagicMock()
mock_ssm = MagicMock()

mock_ecs.describe_services.return_value = {
    "services": [
        {
            "taskDefinition": "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task-def:1",
            "desiredCount": 1,
            "runningCount": 1,
            "deployments": [
                {
                    "status": "PRIMARY",
                    "rolloutState": "COMPLETED",
                    "taskDefinition": "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task-def:2",
                }
            ],
        }
    ]
}
mock_ecs.describe_task_definition.return_value = {
    "taskDefinition": {
        "family": "test-task-def",
        "taskRoleArn": "arn:aws:iam::123456789012:role/test-role",
        "executionRoleArn": "arn:aws:iam::123456789012:role/test-execution-role",
        "networkMode": "awsvpc",
        "requiresCompatibilities": ["FARGATE"],
        "cpu": "256",
        "memory": "512",
        "containerDefinitions": [
            {
                "name": "test-container",
                "environment": [
                    {"name": "EXISTING_VAR", "value": "existing_value"},
                    {"name": "TO_UPDATE", "value": "old_value"},
                ],
            }
        ],
    }
}
mock_ecs.register_task_definition.return_value = {
    "taskDefinition": {"taskDefinitionArn": "arn:aws:ecs:us-east-1:123456789012:task-definition/test-task-def:2"}
}
mock_ecs.update_service.return_value = {}

mock_cfn.describe_stack_resources.return_value = {
    "StackResources": [
        {
            "ResourceType": "AWS::ECS::Service",
            "PhysicalResourceId": "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service",
        },
        {
            "ResourceType": "AWS::ECS::Cluster",
            "PhysicalResourceId": "arn:aws:ecs:us-east-1:123456789012:cluster/test-cluster",
        },
    ]
}


def mock_boto3_client(*args, **kwargs):
    service = args[0] if args else kwargs.get("service_name", kwargs.get("service"))
    if service == "ecs":
        return mock_ecs
    if service == "cloudformation":
        return mock_cfn
    if service == "application-autoscaling":
        return mock_app_autoscaling
    if service == "ssm":
        return mock_ssm
    return MagicMock()


patch("boto3.client", side_effect=mock_boto3_client).start()

# Import state machine functions
from mcp_server.state_machine.update_mcp_server import (  # noqa: E402
    handle_ecs_update,
    handle_finish_update,
    handle_job_intake,
    handle_poll_capacity,
    handle_poll_ecs_deployment,
)


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context."""
    return SimpleNamespace(
        function_name="test_function",
        function_version="$LATEST",
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test_function",
        memory_limit_in_mb=128,
        aws_request_id="test-request-id",
        log_group_name="/aws/lambda/test_function",
        log_stream_name="2024/03/27/[$LATEST]test123",
    )


@pytest.fixture(scope="function")
def dynamodb():
    """Create a mock DynamoDB service."""
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture(scope="function")
def mcp_servers_table(dynamodb):
    """Create a mock DynamoDB table for hosted MCP servers."""
    table = dynamodb.create_table(
        TableName="mcp-servers-table",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return table


@pytest.fixture
def in_service_server(mcp_servers_table):
    item = {
        "id": "server-inservice",
        "name": "Test Hosted MCP Server",
        "status": "InService",
        "stack_name": "test-stack",
        "environment": {"EXISTING_VAR": "existing_value"},
        "cpu": 256,
        "memoryLimitMiB": 512,
        "autoScalingConfig": {"minCapacity": 1, "maxCapacity": 4, "cooldown": 60},
    }
    mcp_servers_table.put_item(Item=item)
    return item


@pytest.fixture
def stopped_server(mcp_servers_table):
    item = {
        "id": "server-stopped",
        "name": "Test Hosted MCP Server",
        "status": "Stopped",
        "stack_name": "test-stack",
        "autoScalingConfig": {"minCapacity": 2, "maxCapacity": 4, "cooldown": 60},
    }
    mcp_servers_table.put_item(Item=item)
    return item


def test_handle_job_intake_enable_flow(mcp_servers_table, stopped_server, lambda_context):
    with patch("mcp_server.state_machine.update_mcp_server.mcp_servers_table", mcp_servers_table):
        result = handle_job_intake({"server_id": "server-stopped", "update_payload": {"enabled": True}}, lambda_context)
        assert result["has_capacity_update"] is True
        assert result["current_server_status"] == "Starting"
        # Ensure we attempted to scale service to min capacity
        mock_ecs.update_service.assert_called()


def test_handle_job_intake_disable_flow(mcp_servers_table, in_service_server, lambda_context):
    with patch("mcp_server.state_machine.update_mcp_server.mcp_servers_table", mcp_servers_table):
        result = handle_job_intake(
            {"server_id": "server-inservice", "update_payload": {"enabled": False}}, lambda_context
        )
        assert result["is_disable"] is True
        assert result["current_server_status"] == "Stopping"
        mock_ecs.update_service.assert_called()


def test_handle_job_intake_autoscaling_update(mcp_servers_table, in_service_server, lambda_context):
    with patch("mcp_server.state_machine.update_mcp_server.mcp_servers_table", mcp_servers_table):
        result = handle_job_intake(
            {
                "server_id": "server-inservice",
                "update_payload": {"autoScalingConfig": {"minCapacity": 2, "maxCapacity": 6, "cooldown": 120}},
            },
            lambda_context,
        )
        assert result["current_server_status"] == "Updating"
        mock_app_autoscaling.register_scalable_target.assert_called()


def test_handle_job_intake_container_updates_trigger_ecs(mcp_servers_table, in_service_server, lambda_context):
    with patch("mcp_server.state_machine.update_mcp_server.mcp_servers_table", mcp_servers_table):
        result = handle_job_intake(
            {
                "server_id": "server-inservice",
                "update_payload": {
                    "environment": {"NEW_ENV": "value", "TO_UPDATE": "LISA_MARKED_FOR_DELETION"},
                    "cpu": 512,
                    "memoryLimitMiB": 1024,
                    "containerHealthCheckConfig": {
                        "command": ["CMD-SHELL", "echo ok"],
                        "interval": 30,
                        "timeout": 5,
                        "startPeriod": 0,
                        "retries": 3,
                    },
                },
            },
            lambda_context,
        )
        assert result["needs_ecs_update"] is True
        assert "container_metadata" in result
        assert "env_vars_to_delete" in result["container_metadata"]


def test_handle_ecs_update_and_polling(mcp_servers_table, in_service_server, lambda_context):
    with patch("mcp_server.state_machine.update_mcp_server.mcp_servers_table", mcp_servers_table):
        res = handle_ecs_update(
            {"server_id": "server-inservice", "container_metadata": {"env_vars_to_delete": ["TO_UPDATE"]}},
            lambda_context,
        )
        assert "new_task_definition_arn" in res
        assert res["ecs_service_arn"].endswith("/test-service")
        poll_res = handle_poll_ecs_deployment(
            {
                "server_id": "server-inservice",
                "ecs_cluster_arn": "cluster",
                "ecs_service_arn": "service",
                "new_task_definition_arn": res["new_task_definition_arn"],
                "remaining_ecs_polls": 10,
            },
            lambda_context,
        )
        assert poll_res["should_continue_ecs_polling"] is False


def test_handle_poll_capacity_flows(mcp_servers_table, in_service_server, lambda_context):
    with patch("mcp_server.state_machine.update_mcp_server.mcp_servers_table", mcp_servers_table):
        # Healthy (desired == running)
        result1 = handle_poll_capacity(
            {"server_id": "server-inservice", "stack_name": "test-stack", "remaining_capacity_polls": 5}, lambda_context
        )
        assert result1["should_continue_capacity_polling"] is False
        # In progress (desired != running)
        mock_ecs.describe_services.return_value["services"][0]["runningCount"] = 0
        result2 = handle_poll_capacity(
            {"server_id": "server-inservice", "stack_name": "test-stack", "remaining_capacity_polls": 5}, lambda_context
        )
        assert result2["should_continue_capacity_polling"] is True
        # Timeout
        result3 = handle_poll_capacity(
            {"server_id": "server-inservice", "stack_name": "test-stack", "remaining_capacity_polls": 1}, lambda_context
        )
        assert result3["should_continue_capacity_polling"] is False
        assert "polling_error" in result3


def test_handle_finish_update_flows(mcp_servers_table, stopped_server, lambda_context):
    with patch("mcp_server.state_machine.update_mcp_server.mcp_servers_table", mcp_servers_table):
        # Successful enable flow
        result = handle_finish_update(
            {
                "server_id": "server-stopped",
                "stack_name": "test-stack",
                "has_capacity_update": True,
                "is_disable": False,
                "initial_server_status": "Stopped",
            },
            lambda_context,
        )
        assert result["current_server_status"] == "InService"
        # Disable flow
        item = {
            "id": "server-inservice-2",
            "name": "Another",
            "status": "Stopping",
            "stack_name": "test-stack",
            "autoScalingConfig": {"minCapacity": 1, "maxCapacity": 2},
        }
        mcp_servers_table.put_item(Item=item)
        result2 = handle_finish_update(
            {
                "server_id": "server-inservice-2",
                "stack_name": "test-stack",
                "has_capacity_update": False,
                "is_disable": True,
                "initial_server_status": "InService",
            },
            lambda_context,
        )
        assert result2["current_server_status"] == "Stopped"


def test_connections_table_updates(mcp_servers_table, in_service_server, lambda_context, dynamodb):
    # Prepare connections table and SSM
    connections_table = dynamodb.create_table(
        TableName="connections-table",
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}, {"AttributeName": "owner", "KeyType": "RANGE"}],
        AttributeDefinitions=[
            {"AttributeName": "id", "AttributeType": "S"},
            {"AttributeName": "owner", "AttributeType": "S"},
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    # Seed entry
    connections_table.put_item(Item={"id": "server-inservice", "owner": "lisa:public", "status": "active"})

    with patch("mcp_server.state_machine.update_mcp_server.mcp_servers_table", mcp_servers_table), patch(
        "mcp_server.state_machine.update_mcp_server.ssm_client.get_parameter",
        return_value={"Parameter": {"Value": "connections-table"}},
    ), patch("mcp_server.state_machine.update_mcp_server.ddbResource", dynamodb):
        # Disable updates status to inactive
        handle_job_intake({"server_id": "server-inservice", "update_payload": {"enabled": False}}, lambda_context)
        row = connections_table.get_item(Key={"id": "server-inservice", "owner": "lisa:public"}).get("Item")
        assert row["status"] == "inactive"

        # Metadata update updates description and groups
        connections_table.put_item(Item={"id": "server-inservice", "owner": "lisa:public", "status": "active"})
        handle_job_intake(
            {
                "server_id": "server-inservice",
                "update_payload": {"description": "Desc", "groups": ["alpha", "beta"]},
            },
            lambda_context,
        )
        row2 = connections_table.get_item(Key={"id": "server-inservice", "owner": "lisa:public"}).get("Item")
        assert row2["description"] == "Desc"
        assert set(row2["groups"]) == {"group:alpha", "group:beta"}


def test_handle_ecs_update_error_no_stack(mcp_servers_table, lambda_context):
    mcp_servers_table.put_item(Item={"id": "no-stack", "status": "InService"})
    with patch("mcp_server.state_machine.update_mcp_server.mcp_servers_table", mcp_servers_table):
        res = handle_ecs_update({"server_id": "no-stack"}, lambda_context)
        assert "ecs_update_error" in res
