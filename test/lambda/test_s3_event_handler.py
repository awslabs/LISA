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

"""Unit tests for S3 event handler lambda function."""

import json
import os
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from botocore.exceptions import ClientError

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

mock_env = {
    "AWS_ACCESS_KEY_ID": "testing",
    "AWS_SECRET_ACCESS_KEY": "testing",
    "AWS_SECURITY_TOKEN": "testing",
    "AWS_SESSION_TOKEN": "testing",
    "AWS_DEFAULT_REGION": "us-east-1",
    "AWS_REGION": "us-east-1",
    "DEPLOYMENT_PREFIX": "/test-deployment",
    "API_NAME": "serve",
    "ECS_CLUSTER_NAME": "test-deployment-serve",
    "MCPWORKBENCH_SERVICE_NAME": "MCPWORKBENCH",
}


@pytest.fixture(autouse=True, scope="function")
def mock_common():
    """Ensure complete test isolation with fresh environment."""
    with patch.dict("os.environ", mock_env, clear=True):
        yield


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context."""
    return SimpleNamespace(
        function_name="s3_event_handler",
        function_version="$LATEST",
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:s3_event_handler",
        memory_limit_in_mb=128,
        aws_request_id="test-request-id",
        log_group_name="/aws/lambda/s3_event_handler",
        log_stream_name="2024/03/27/[$LATEST]test123",
    )


@pytest.fixture
def sample_s3_event():
    """Create a sample S3 event from EventBridge."""
    return {
        "version": "0",
        "id": "test-event-id",
        "detail-type": "Object Created",
        "source": "aws.s3",
        "account": "123456789012",
        "time": "2024-03-27T12:00:00Z",
        "region": "us-east-1",
        "detail": {
            "version": "0",
            "bucket": {"name": "test-deployment-dev-mcpworkbench"},
            "object": {"key": "test-tool.py", "size": 1024, "etag": "test-etag"},
            "eventName": "s3:ObjectCreated:Put",
            "eventSource": "aws:s3",
        },
    }


def test_handler_success(lambda_context, sample_s3_event):
    """Test successful S3 event handling."""
    # Mock ECS client response
    mock_ecs_response = {
        "service": {
            "serviceName": "MCPWORKBENCH",
            "deployments": [
                {
                    "id": "arn:aws:ecs:us-east-1:123456789012:service/test-cluster/test-service/deployment-123",
                    "status": "PRIMARY",
                }
            ],
        }
    }

    # Import and test the function
    from mcp_workbench.s3_event_handler import handler

    with patch("mcp_workbench.s3_event_handler.ecs_client") as mock_ecs_client:
        mock_ecs_client.update_service.return_value = mock_ecs_response

        response = handler(sample_s3_event, lambda_context)

    # Verify the response
    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["message"] == "MCPWORKBENCH service redeployment triggered successfully"
    assert body["bucket"] == "test-deployment-dev-mcpworkbench"
    assert body["event"] == "s3:ObjectCreated:Put"
    assert body["cluster"] == "test-deployment-serve"
    assert body["service"] == "MCPWORKBENCH"

    # Verify ECS client was called correctly
    mock_ecs_client.update_service.assert_called_once_with(
        cluster="test-deployment-serve", service="MCPWORKBENCH", forceNewDeployment=True
    )


def test_handler_missing_bucket_name(lambda_context):
    """Test handling of event with missing bucket name."""
    event = {"detail": {"eventName": "s3:ObjectCreated:Put"}}

    from mcp_workbench.s3_event_handler import handler

    response = handler(event, lambda_context)

    assert response["statusCode"] == 400
    assert "Missing bucket name" in response["body"]


def test_handler_ecs_service_not_found(lambda_context, sample_s3_event):
    """Test handling of ECS service not found error."""
    from mcp_workbench.s3_event_handler import handler

    # Mock ECS client to raise ServiceNotFoundException
    with patch("mcp_workbench.s3_event_handler.ecs_client") as mock_ecs_client:
        mock_ecs_client.update_service.side_effect = ClientError(
            error_response={"Error": {"Code": "ServiceNotFoundException", "Message": "Service not found"}},
            operation_name="UpdateService",
        )

        response = handler(sample_s3_event, lambda_context)

    assert response["statusCode"] == 500
    assert "Error" in response["body"]


def test_handler_ecs_cluster_not_found(lambda_context, sample_s3_event):
    """Test handling of ECS cluster not found error."""
    from mcp_workbench.s3_event_handler import handler

    # Mock ECS client to raise ClusterNotFoundException
    with patch("mcp_workbench.s3_event_handler.ecs_client") as mock_ecs_client:
        mock_ecs_client.update_service.side_effect = ClientError(
            error_response={"Error": {"Code": "ClusterNotFoundException", "Message": "Cluster not found"}},
            operation_name="UpdateService",
        )

        response = handler(sample_s3_event, lambda_context)

    assert response["statusCode"] == 500
    assert "Error" in response["body"]


def test_get_cluster_name_from_env():
    """Test getting cluster name from environment variable."""
    from mcp_workbench.s3_event_handler import get_cluster_name

    cluster_name = get_cluster_name()
    assert cluster_name == "test-deployment-serve"


def test_get_cluster_name_fallback():
    """Test getting cluster name with fallback logic."""
    from mcp_workbench.s3_event_handler import get_cluster_name

    # Test without ECS_CLUSTER_NAME env var
    with patch.dict(os.environ, {k: v for k, v in mock_env.items() if k != "ECS_CLUSTER_NAME"}):
        with patch("mcp_workbench.s3_event_handler.ssm_client") as mock_ssm:
            # Mock SSM parameter not found, should use fallback logic
            mock_ssm.get_parameter.side_effect = ClientError(
                error_response={"Error": {"Code": "ParameterNotFound"}}, operation_name="GetParameter"
            )

            cluster_name = get_cluster_name()
            assert cluster_name == "test-deployment-serve"


def test_get_service_name_from_env():
    """Test getting service name from environment variable."""
    from mcp_workbench.s3_event_handler import get_service_name

    service_name = get_service_name()
    assert service_name == "MCPWORKBENCH"


def test_get_service_name_fallback():
    """Test getting service name with fallback logic."""
    from mcp_workbench.s3_event_handler import get_service_name

    # Test without MCPWORKBENCH_SERVICE_NAME env var
    with patch.dict(os.environ, {k: v for k, v in mock_env.items() if k != "MCPWORKBENCH_SERVICE_NAME"}):
        service_name = get_service_name()
        assert service_name == "MCPWORKBENCH"


def test_force_service_deployment_success():
    """Test successful ECS service deployment."""
    from mcp_workbench.s3_event_handler import force_service_deployment

    mock_response = {"service": {"serviceName": "MCPWORKBENCH", "deployments": [{"id": "deployment-123"}]}}

    with patch("mcp_workbench.s3_event_handler.ecs_client") as mock_ecs_client:
        mock_ecs_client.update_service.return_value = mock_response

        response = force_service_deployment("test-cluster", "MCPWORKBENCH")

        assert response == mock_response
        mock_ecs_client.update_service.assert_called_once_with(
            cluster="test-cluster", service="MCPWORKBENCH", forceNewDeployment=True
        )


def test_force_service_deployment_service_not_found():
    """Test ECS service deployment with service not found."""
    from mcp_workbench.s3_event_handler import force_service_deployment

    with patch("mcp_workbench.s3_event_handler.ecs_client") as mock_ecs_client:
        mock_ecs_client.update_service.side_effect = ClientError(
            error_response={"Error": {"Code": "ServiceNotFoundException", "Message": "Service not found"}},
            operation_name="UpdateService",
        )

        with pytest.raises(ClientError):
            force_service_deployment("test-cluster", "MCPWORKBENCH")


def test_validate_s3_event_valid():
    """Test validation of valid S3 event."""
    from mcp_workbench.s3_event_handler import validate_s3_event

    valid_event = {"source": "aws.s3", "detail-type": "Object Created", "detail": {"bucket": {"name": "test-bucket"}}}

    assert validate_s3_event(valid_event) is True


def test_validate_s3_event_invalid_source():
    """Test validation of S3 event with invalid source."""
    from mcp_workbench.s3_event_handler import validate_s3_event

    invalid_event = {
        "source": "aws.ec2",
        "detail-type": "Object Created",
        "detail": {"bucket": {"name": "test-bucket"}},
    }

    assert validate_s3_event(invalid_event) is False


def test_validate_s3_event_invalid_detail_type():
    """Test validation of S3 event with invalid detail type."""
    from mcp_workbench.s3_event_handler import validate_s3_event

    invalid_event = {
        "source": "aws.s3",
        "detail-type": "Instance State Change",
        "detail": {"bucket": {"name": "test-bucket"}},
    }

    assert validate_s3_event(invalid_event) is False


def test_validate_s3_event_missing_bucket():
    """Test validation of S3 event with missing bucket name."""
    from mcp_workbench.s3_event_handler import validate_s3_event

    invalid_event = {"source": "aws.s3", "detail-type": "Object Created", "detail": {}}

    assert validate_s3_event(invalid_event) is False


def test_validate_s3_event_debug_source():
    """Test validation of S3 event with debug source."""
    from mcp_workbench.s3_event_handler import validate_s3_event

    debug_event = {"source": "debug", "detail-type": "Object Created", "detail": {"bucket": {"name": "test-bucket"}}}

    assert validate_s3_event(debug_event) is True
