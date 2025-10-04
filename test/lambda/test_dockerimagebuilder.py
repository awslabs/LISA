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

"""
Refactored dockerimagebuilder tests using fixture-based mocking instead of global mocks.
This replaces the original test_dockerimagebuilder.py with isolated, maintainable tests.
"""

import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


# Set up test environment variables
@pytest.fixture(autouse=True)
def setup_test_env():
    """Set up test environment variables."""
    env_vars = {
        "AWS_ACCESS_KEY_ID": "testing",
        "AWS_SECRET_ACCESS_KEY": "testing",
        "AWS_SECURITY_TOKEN": "testing",
        "AWS_SESSION_TOKEN": "testing",
        "AWS_DEFAULT_REGION": "us-east-1",
        "AWS_REGION": "us-east-1",
        "LISA_MOUNTS3_DEB_URL": "https://example.com/mounts3.deb",
        "LISA_DOCKER_BUCKET": "test-bucket",
        "LISA_ECR_URI": "123456789012.dkr.ecr.us-east-1.amazonaws.com/test-repo",
        "LISA_INSTANCE_PROFILE": "arn:aws:iam::123456789012:instance-profile/test-profile",
        "LISA_IMAGEBUILDER_VOLUME_SIZE": "20",
        "LISA_SUBNET_ID": "subnet-12345678",
    }

    for key, value in env_vars.items():
        os.environ[key] = value

    yield

    # Cleanup
    for key in env_vars.keys():
        if key in os.environ:
            del os.environ[key]


@pytest.fixture
def dockerimagebuilder_functions():
    """Import dockerimagebuilder functions."""
    import os
    import sys

    # Add lambda directory to path
    lambda_dir = os.path.join(os.path.dirname(__file__), "../../lambda")
    if lambda_dir not in sys.path:
        sys.path.insert(0, lambda_dir)

    import dockerimagebuilder

    return dockerimagebuilder


@pytest.fixture
def mock_boto3_services():
    """Mock boto3 services for dockerimagebuilder."""
    mock_ec2_resource = MagicMock()
    mock_ssm_client = MagicMock()
    mock_instance = MagicMock()
    mock_instance.instance_id = "i-1234567890abcdef0"

    # Configure default responses
    mock_ssm_client.get_parameter.return_value = {"Parameter": {"Value": "ami-12345678"}}
    mock_ec2_resource.create_instances.return_value = [mock_instance]

    return {"ec2_resource": mock_ec2_resource, "ssm_client": mock_ssm_client, "instance": mock_instance}


@pytest.fixture
def sample_event():
    """Sample event for dockerimagebuilder handler."""
    return {"base_image": "python:3.9-slim", "layer_to_add": "test-layer"}


class TestDockerImageBuilder:
    """Test dockerimagebuilder handler function - REFACTORED VERSION."""

    def test_handler_success(self, sample_event, lambda_context, mock_boto3_services, dockerimagebuilder_functions):
        """Test successful handler execution."""
        with patch("dockerimagebuilder.boto3") as mock_boto3:
            # Setup mocks
            mock_boto3.resource.return_value = mock_boto3_services["ec2_resource"]
            mock_boto3.client.return_value = mock_boto3_services["ssm_client"]

            # Call handler
            result = dockerimagebuilder_functions.handler(sample_event, lambda_context)

            # Verify result
            assert result["instance_id"] == "i-1234567890abcdef0"
            assert "image_tag" in result

            # Verify SSM call
            mock_boto3_services["ssm_client"].get_parameter.assert_called_once_with(
                Name="/aws/service/ami-amazon-linux-latest/amzn2-ami-hvm-x86_64-gp2"
            )

            # Verify EC2 instance creation
            mock_boto3_services["ec2_resource"].create_instances.assert_called_once()
            call_args = mock_boto3_services["ec2_resource"].create_instances.call_args[1]
            assert call_args["ImageId"] == "ami-12345678"
            assert call_args["MinCount"] == 1
            assert call_args["MaxCount"] == 1
            assert call_args["InstanceType"] == "m5.large"
            assert call_args["SubnetId"] == "subnet-12345678"
            assert "UserData" in call_args
            assert "python:3.9-slim" in call_args["UserData"]
            assert "test-layer" in call_args["UserData"]

    def test_handler_without_subnet_id(
        self, sample_event, lambda_context, mock_boto3_services, dockerimagebuilder_functions
    ):
        """Test handler execution without subnet ID."""
        # Temporarily remove subnet ID from environment
        original_subnet_id = os.environ.pop("LISA_SUBNET_ID", None)

        try:
            with patch("dockerimagebuilder.boto3") as mock_boto3:
                # Setup mocks
                mock_boto3.resource.return_value = mock_boto3_services["ec2_resource"]
                mock_boto3.client.return_value = mock_boto3_services["ssm_client"]

                # Call handler
                result = dockerimagebuilder_functions.handler(sample_event, lambda_context)

                # Verify result
                assert result["instance_id"] == "i-1234567890abcdef0"
                assert "image_tag" in result

                # Verify EC2 instance creation without SubnetId
                call_args = mock_boto3_services["ec2_resource"].create_instances.call_args[1]
                assert "SubnetId" not in call_args
        finally:
            # Restore subnet ID
            if original_subnet_id:
                os.environ["LISA_SUBNET_ID"] = original_subnet_id

    def test_handler_client_error(
        self, sample_event, lambda_context, mock_boto3_services, dockerimagebuilder_functions
    ):
        """Test handler with ClientError."""
        with patch("dockerimagebuilder.boto3") as mock_boto3:
            # Setup mocks
            mock_boto3.resource.return_value = mock_boto3_services["ec2_resource"]
            mock_boto3.client.return_value = mock_boto3_services["ssm_client"]

            # Mock create_instances to raise ClientError
            mock_boto3_services["ec2_resource"].create_instances.side_effect = ClientError(
                {"Error": {"Code": "InvalidParameterValue", "Message": "Test error"}}, "CreateInstances"
            )

            # Call handler and expect exception
            with pytest.raises(ClientError):
                dockerimagebuilder_functions.handler(sample_event, lambda_context)

    def test_handler_ssm_error(self, sample_event, lambda_context, mock_boto3_services, dockerimagebuilder_functions):
        """Test handler with SSM ClientError."""
        with patch("dockerimagebuilder.boto3") as mock_boto3:
            # Setup mocks
            mock_boto3.resource.return_value = mock_boto3_services["ec2_resource"]
            mock_boto3.client.return_value = mock_boto3_services["ssm_client"]

            # Mock get_parameter to raise ClientError
            mock_boto3_services["ssm_client"].get_parameter.side_effect = ClientError(
                {"Error": {"Code": "ParameterNotFound", "Message": "Test error"}}, "GetParameter"
            )

            # Call handler and expect exception
            with pytest.raises(ClientError):
                dockerimagebuilder_functions.handler(sample_event, lambda_context)

    def test_user_data_template_rendering(
        self, sample_event, lambda_context, mock_boto3_services, dockerimagebuilder_functions
    ):
        """Test that user data template is properly rendered."""
        with patch("dockerimagebuilder.boto3") as mock_boto3:
            # Setup mocks
            mock_boto3.resource.return_value = mock_boto3_services["ec2_resource"]
            mock_boto3.client.return_value = mock_boto3_services["ssm_client"]

            # Call handler
            result = dockerimagebuilder_functions.handler(sample_event, lambda_context)

            # Verify user data contains all expected replacements
            call_args = mock_boto3_services["ec2_resource"].create_instances.call_args[1]
            user_data = call_args["UserData"]

            assert "us-east-1" in user_data  # AWS_REGION
            assert "test-bucket" in user_data  # BUCKET_NAME
            assert "test-layer" in user_data  # LAYER_TO_ADD
            assert "python:3.9-slim" in user_data  # BASE_IMAGE
            assert "https://example.com/mounts3.deb" in user_data  # MOUNTS3_DEB_URL
            assert "123456789012.dkr.ecr.us-east-1.amazonaws.com/test-repo" in user_data  # ECR_URI
            assert result["image_tag"] in user_data  # IMAGE_ID

    def test_handler_with_different_instance_type(
        self, sample_event, lambda_context, mock_boto3_services, dockerimagebuilder_functions
    ):
        """Test handler uses correct instance type."""
        with patch("dockerimagebuilder.boto3") as mock_boto3:
            # Setup mocks
            mock_boto3.resource.return_value = mock_boto3_services["ec2_resource"]
            mock_boto3.client.return_value = mock_boto3_services["ssm_client"]

            # Call handler
            dockerimagebuilder_functions.handler(sample_event, lambda_context)

            # Verify EC2 instance creation uses correct instance type
            call_args = mock_boto3_services["ec2_resource"].create_instances.call_args[1]
            assert call_args["InstanceType"] == "m5.large"

    def test_handler_includes_instance_profile(
        self, sample_event, lambda_context, mock_boto3_services, dockerimagebuilder_functions
    ):
        """Test handler includes instance profile in EC2 creation."""
        with patch("dockerimagebuilder.boto3") as mock_boto3:
            # Setup mocks
            mock_boto3.resource.return_value = mock_boto3_services["ec2_resource"]
            mock_boto3.client.return_value = mock_boto3_services["ssm_client"]

            # Call handler
            dockerimagebuilder_functions.handler(sample_event, lambda_context)

            # Verify EC2 instance creation includes IAM instance profile
            call_args = mock_boto3_services["ec2_resource"].create_instances.call_args[1]
            assert "IamInstanceProfile" in call_args
            assert call_args["IamInstanceProfile"]["Arn"] == "arn:aws:iam::123456789012:instance-profile/test-profile"

    def test_handler_block_device_mapping(
        self, sample_event, lambda_context, mock_boto3_services, dockerimagebuilder_functions
    ):
        """Test handler includes correct block device mapping."""
        with patch("dockerimagebuilder.boto3") as mock_boto3:
            # Setup mocks
            mock_boto3.resource.return_value = mock_boto3_services["ec2_resource"]
            mock_boto3.client.return_value = mock_boto3_services["ssm_client"]

            # Call handler
            dockerimagebuilder_functions.handler(sample_event, lambda_context)

            # Verify EC2 instance creation includes block device mapping
            call_args = mock_boto3_services["ec2_resource"].create_instances.call_args[1]
            assert "BlockDeviceMappings" in call_args

            # Verify volume size from environment variable
            block_devices = call_args["BlockDeviceMappings"]
            assert len(block_devices) > 0
            assert block_devices[0]["Ebs"]["VolumeSize"] == 20  # From LISA_IMAGEBUILDER_VOLUME_SIZE

    def test_handler_empty_event_fields(self, lambda_context, mock_boto3_services, dockerimagebuilder_functions):
        """Test handler with empty event fields."""
        event = {"base_image": "", "layer_to_add": ""}

        with patch("dockerimagebuilder.boto3") as mock_boto3:
            # Setup mocks
            mock_boto3.resource.return_value = mock_boto3_services["ec2_resource"]
            mock_boto3.client.return_value = mock_boto3_services["ssm_client"]

            # Call handler
            result = dockerimagebuilder_functions.handler(event, lambda_context)

            # Verify result is still returned
            assert result["instance_id"] == "i-1234567890abcdef0"
            assert "image_tag" in result

            # Verify user data contains empty values
            call_args = mock_boto3_services["ec2_resource"].create_instances.call_args[1]
            user_data = call_args["UserData"]
            assert user_data is not None  # Should still have user data template

    def test_handler_missing_event_fields(self, lambda_context, mock_boto3_services, dockerimagebuilder_functions):
        """Test handler with missing event fields."""
        event = {}  # No base_image or layer_to_add

        with patch("dockerimagebuilder.boto3") as mock_boto3:
            # Setup mocks
            mock_boto3.resource.return_value = mock_boto3_services["ec2_resource"]
            mock_boto3.client.return_value = mock_boto3_services["ssm_client"]

            # Call handler - should raise KeyError for missing required fields
            with pytest.raises(KeyError, match="base_image"):
                dockerimagebuilder_functions.handler(event, lambda_context)


class TestImageTagGeneration:
    """Test image tag generation - REFACTORED VERSION."""

    def test_image_tag_format(self, sample_event, lambda_context, mock_boto3_services, dockerimagebuilder_functions):
        """Test that image tag has expected format."""
        with patch("dockerimagebuilder.boto3") as mock_boto3:
            # Setup mocks
            mock_boto3.resource.return_value = mock_boto3_services["ec2_resource"]
            mock_boto3.client.return_value = mock_boto3_services["ssm_client"]

            # Call handler
            result = dockerimagebuilder_functions.handler(sample_event, lambda_context)

            # Verify image tag format
            image_tag = result["image_tag"]
            assert isinstance(image_tag, str)
            assert len(image_tag) > 0

            # Image tag should be included in user data
            call_args = mock_boto3_services["ec2_resource"].create_instances.call_args[1]
            user_data = call_args["UserData"]
            assert image_tag in user_data


class TestEnvironmentVariableHandling:
    """Test environment variable handling - REFACTORED VERSION."""

    def test_missing_environment_variables(
        self, sample_event, lambda_context, mock_boto3_services, dockerimagebuilder_functions
    ):
        """Test handler behavior with missing environment variables."""
        # Temporarily remove some environment variables
        original_vars = {}
        vars_to_remove = ["LISA_DOCKER_BUCKET"]

        for var in vars_to_remove:
            original_vars[var] = os.environ.pop(var, None)

        try:
            with patch("dockerimagebuilder.boto3") as mock_boto3:
                # Setup mocks
                mock_boto3.resource.return_value = mock_boto3_services["ec2_resource"]
                mock_boto3.client.return_value = mock_boto3_services["ssm_client"]

                # Call handler - should raise KeyError for missing required env vars
                with pytest.raises(KeyError, match="LISA_DOCKER_BUCKET"):
                    dockerimagebuilder_functions.handler(sample_event, lambda_context)
        finally:
            # Restore environment variables
            for var, value in original_vars.items():
                if value is not None:
                    os.environ[var] = value
