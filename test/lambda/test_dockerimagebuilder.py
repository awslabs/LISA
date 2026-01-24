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

"""Test dockerimagebuilder module."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["LISA_MOUNTS3_DEB_URL"] = "https://example.com/mounts3.deb"
os.environ["LISA_DOCKER_BUCKET"] = "test-bucket"
os.environ["LISA_ECR_URI"] = "123456789012.dkr.ecr.us-east-1.amazonaws.com/test-repo"
os.environ["LISA_INSTANCE_PROFILE"] = "arn:aws:iam::123456789012:instance-profile/test-profile"
os.environ["LISA_IMAGEBUILDER_VOLUME_SIZE"] = "20"
os.environ["LISA_SUBNET_ID"] = "subnet-12345678"

from dockerimagebuilder import handler


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context."""
    context = MagicMock()
    context.log_group_name = "/aws/lambda/test-function"
    return context


def test_handler_success(lambda_context):
    """Test successful handler execution."""
    event = {"base_image": "public.ecr.aws/docker/library/python:3.13-slim", "layer_to_add": "test-layer"}

    # Mock boto3 resources and clients
    mock_ec2_resource = MagicMock()
    mock_ssm_client = MagicMock()
    mock_instance = MagicMock()
    mock_instance.instance_id = "i-1234567890abcdef0"

    with patch("dockerimagebuilder.boto3") as mock_boto3:
        # Setup mocks
        mock_boto3.resource.return_value = mock_ec2_resource
        mock_boto3.client.return_value = mock_ssm_client

        mock_ssm_client.get_parameter.return_value = {"Parameter": {"Value": "ami-12345678"}}

        mock_ec2_resource.create_instances.return_value = [mock_instance]

        # Call handler
        result = handler(event, lambda_context)

        # Verify result
        assert result["instance_id"] == "i-1234567890abcdef0"
        assert "image_tag" in result

        # Verify SSM call
        mock_ssm_client.get_parameter.assert_called_once_with(
            Name="/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
        )

        # Verify EC2 instance creation
        mock_ec2_resource.create_instances.assert_called_once()
        call_args = mock_ec2_resource.create_instances.call_args[1]
        assert call_args["ImageId"] == "ami-12345678"
        assert call_args["MinCount"] == 1
        assert call_args["MaxCount"] == 1
        assert call_args["InstanceType"] == "m5.large"
        assert call_args["SubnetId"] == "subnet-12345678"
        assert "UserData" in call_args
        assert "public.ecr.aws/docker/library/python:3.13-slim" in call_args["UserData"]
        assert "test-layer" in call_args["UserData"]


def test_handler_without_subnet_id(lambda_context):
    """Test handler execution without subnet ID."""
    # Remove subnet ID from environment
    original_subnet_id = os.environ.pop("LISA_SUBNET_ID", None)

    try:
        event = {"base_image": "public.ecr.aws/docker/library/python:3.13-slim", "layer_to_add": "test-layer"}

        # Mock boto3 resources and clients
        mock_ec2_resource = MagicMock()
        mock_ssm_client = MagicMock()
        mock_instance = MagicMock()
        mock_instance.instance_id = "i-1234567890abcdef0"

        with patch("dockerimagebuilder.boto3") as mock_boto3:
            # Setup mocks
            mock_boto3.resource.return_value = mock_ec2_resource
            mock_boto3.client.return_value = mock_ssm_client

            mock_ssm_client.get_parameter.return_value = {"Parameter": {"Value": "ami-12345678"}}

            mock_ec2_resource.create_instances.return_value = [mock_instance]

            # Call handler
            result = handler(event, lambda_context)

            # Verify result
            assert result["instance_id"] == "i-1234567890abcdef0"
            assert "image_tag" in result

            # Verify EC2 instance creation without SubnetId
            call_args = mock_ec2_resource.create_instances.call_args[1]
            assert "SubnetId" not in call_args
    finally:
        # Restore subnet ID
        if original_subnet_id:
            os.environ["LISA_SUBNET_ID"] = original_subnet_id


def test_handler_client_error(lambda_context):
    """Test handler with ClientError."""
    event = {"base_image": "public.ecr.aws/docker/library/python:3.13-slim", "layer_to_add": "test-layer"}

    # Mock boto3 resources and clients
    mock_ec2_resource = MagicMock()
    mock_ssm_client = MagicMock()

    with patch("dockerimagebuilder.boto3") as mock_boto3:
        # Setup mocks
        mock_boto3.resource.return_value = mock_ec2_resource
        mock_boto3.client.return_value = mock_ssm_client

        mock_ssm_client.get_parameter.return_value = {"Parameter": {"Value": "ami-12345678"}}

        # Mock create_instances to raise ClientError
        mock_ec2_resource.create_instances.side_effect = ClientError(
            {"Error": {"Code": "InvalidParameterValue", "Message": "Test error"}}, "CreateInstances"
        )

        # Call handler and expect exception
        with pytest.raises(ClientError):
            handler(event, lambda_context)


def test_handler_ssm_error(lambda_context):
    """Test handler with SSM ClientError."""
    event = {"base_image": "public.ecr.aws/docker/library/python:3.13-slim", "layer_to_add": "test-layer"}

    # Mock boto3 resources and clients
    mock_ec2_resource = MagicMock()
    mock_ssm_client = MagicMock()

    with patch("dockerimagebuilder.boto3") as mock_boto3:
        # Setup mocks
        mock_boto3.resource.return_value = mock_ec2_resource
        mock_boto3.client.return_value = mock_ssm_client

        # Mock get_parameter to raise ClientError
        mock_ssm_client.get_parameter.side_effect = ClientError(
            {"Error": {"Code": "ParameterNotFound", "Message": "Test error"}}, "GetParameter"
        )

        # Call handler and expect exception
        with pytest.raises(ClientError):
            handler(event, lambda_context)


def test_user_data_template_rendering(lambda_context):
    """Test that user data template is properly rendered."""
    event = {"base_image": "public.ecr.aws/docker/library/python:3.13-slim", "layer_to_add": "test-layer"}

    # Mock boto3 resources and clients
    mock_ec2_resource = MagicMock()
    mock_ssm_client = MagicMock()
    mock_instance = MagicMock()
    mock_instance.instance_id = "i-1234567890abcdef0"

    with patch("dockerimagebuilder.boto3") as mock_boto3:
        # Setup mocks
        mock_boto3.resource.return_value = mock_ec2_resource
        mock_boto3.client.return_value = mock_ssm_client

        mock_ssm_client.get_parameter.return_value = {"Parameter": {"Value": "ami-12345678"}}

        mock_ec2_resource.create_instances.return_value = [mock_instance]

        # Call handler
        result = handler(event, lambda_context)

        # Verify user data contains all expected replacements
        call_args = mock_ec2_resource.create_instances.call_args[1]
        user_data = call_args["UserData"]

        assert "us-east-1" in user_data  # AWS_REGION
        assert "test-bucket" in user_data  # BUCKET_NAME
        assert "test-layer" in user_data  # LAYER_TO_ADD
        assert "public.ecr.aws/docker/library/python:3.13-slim" in user_data  # BASE_IMAGE
        assert "https://example.com/mounts3.deb" in user_data  # MOUNTS3_DEB_URL
        assert "123456789012.dkr.ecr.us-east-1.amazonaws.com/test-repo" in user_data  # ECR_URI
        assert result["image_tag"] in user_data  # IMAGE_ID
