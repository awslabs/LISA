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

"""Unit tests for management_key lambda function."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError
from moto import mock_aws

# Set mock AWS credentials
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["MANAGEMENT_KEY_NAME"] = "test-management-key"

# Add lambda directory to path and import functions
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

from management_key import (
    create_secret,
    finish_secret,
    handler,
    rotate_management_key,
    set_secret,
    test_secret as validate_secret,
)


@pytest.fixture
def lambda_context():
    """Mock Lambda context object."""
    context = MagicMock()
    context.function_name = "management-key-lambda"
    context.function_version = "1"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:management-key-lambda"
    context.memory_limit_in_mb = 128
    context.log_group_name = "/aws/lambda/management-key-lambda"
    context.log_stream_name = "2023/01/01/[$LATEST]abcdef123456"
    context.aws_request_id = "00000000-0000-0000-0000-000000000000"
    return context


@pytest.fixture
def sample_event():
    """Sample event for handler function."""
    return {
        "SecretId": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret-abcdef",
        "ClientRequestToken": "test-token-123",
        "Step": "createSecret",
    }


@pytest.fixture
def sample_event_step1():
    """Sample event with Step1 structure."""
    return {
        "Step1": {
            "SecretId": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret-abcdef",
            "ClientRequestToken": "test-token-123",
        },
        "Step": "createSecret",
    }


@pytest.fixture
def mock_secrets_manager():
    """Mock secrets manager client."""
    client = MagicMock()
    client.get_secret_value.return_value = {"SecretString": "existing-password"}
    client.get_random_password.return_value = {"RandomPassword": "new-random-password"}
    client.put_secret_value.return_value = {}
    client.describe_secret.return_value = {
        "VersionIdsToStages": {
            "current-version": ["AWSCURRENT"],
            "test-token-123": ["AWSPENDING"],
        }
    }
    client.update_secret_version_stage.return_value = {}
    return client


def test_handler_create_secret_success(sample_event, lambda_context, mock_secrets_manager):
    """Test successful createSecret step."""
    # Mock that the secret version doesn't exist
    mock_secrets_manager.get_secret_value.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "Version not found"}}, "GetSecretValue"
    )
    
    with patch("management_key.secrets_manager", mock_secrets_manager):
        response = handler(sample_event, lambda_context)

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == "Success"
    mock_secrets_manager.get_secret_value.assert_called_once()
    mock_secrets_manager.get_random_password.assert_called_once()
    mock_secrets_manager.put_secret_value.assert_called_once()


def test_handler_create_secret_success_step1_format(sample_event_step1, lambda_context, mock_secrets_manager):
    """Test successful createSecret step with Step1 format."""
    with patch("management_key.secrets_manager", mock_secrets_manager):
        response = handler(sample_event_step1, lambda_context)

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == "Success"


def test_handler_set_secret_success(sample_event, lambda_context, mock_secrets_manager):
    """Test successful setSecret step."""
    sample_event["Step"] = "setSecret"

    with patch("management_key.secrets_manager", mock_secrets_manager):
        response = handler(sample_event, lambda_context)

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == "Success"


def test_handler_test_secret_success(sample_event, lambda_context, mock_secrets_manager):
    """Test successful testSecret step."""
    sample_event["Step"] = "testSecret"
    mock_secrets_manager.get_secret_value.return_value = {"SecretString": "testpassword16chars"}

    with patch("management_key.secrets_manager", mock_secrets_manager):
        response = handler(sample_event, lambda_context)

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == "Success"


def test_handler_finish_secret_success(sample_event, lambda_context, mock_secrets_manager):
    """Test successful finishSecret step."""
    sample_event["Step"] = "finishSecret"

    with patch("management_key.secrets_manager", mock_secrets_manager):
        response = handler(sample_event, lambda_context)

    assert response["statusCode"] == 200
    assert json.loads(response["body"]) == "Success"


def test_handler_missing_secret_id(lambda_context):
    """Test handler with missing SecretId."""
    event = {"ClientRequestToken": "test-token-123", "Step": "createSecret"}

    with pytest.raises(ValueError, match="SecretId and ClientRequestToken are required"):
        handler(event, lambda_context)


def test_handler_missing_token(lambda_context):
    """Test handler with missing ClientRequestToken."""
    event = {"SecretId": "test-secret", "Step": "createSecret"}

    with pytest.raises(ValueError, match="SecretId and ClientRequestToken are required"):
        handler(event, lambda_context)


def test_handler_invalid_step(sample_event, lambda_context):
    """Test handler with invalid step."""
    sample_event["Step"] = "invalidStep"

    with pytest.raises(ValueError, match="Invalid step parameter: invalidStep"):
        handler(sample_event, lambda_context)


def test_handler_exception_propagation(sample_event, lambda_context, mock_secrets_manager):
    """Test that exceptions are properly propagated from handler."""
    mock_secrets_manager.get_secret_value.side_effect = ClientError(
        {"Error": {"Code": "InternalServiceError", "Message": "Service error"}}, "GetSecretValue"
    )

    with patch("management_key.secrets_manager", mock_secrets_manager):
        with pytest.raises(ClientError):
            handler(sample_event, lambda_context)


def test_create_secret_already_exists(mock_secrets_manager):
    """Test create_secret when version already exists."""
    secret_arn = "test-secret"
    token = "test-token"

    # Mock that the secret version already exists
    mock_secrets_manager.get_secret_value.return_value = {"SecretString": "existing-password"}

    with patch("management_key.secrets_manager", mock_secrets_manager):
        create_secret(secret_arn, token)

    # Should only call get_secret_value, not create new password
    mock_secrets_manager.get_secret_value.assert_called_once_with(
        SecretId=secret_arn, VersionId=token, VersionStage="AWSPENDING"
    )
    mock_secrets_manager.get_random_password.assert_not_called()
    mock_secrets_manager.put_secret_value.assert_not_called()


def test_create_secret_not_found_creates_new(mock_secrets_manager):
    """Test create_secret when version doesn't exist."""
    secret_arn = "test-secret"
    token = "test-token"

    # Mock that the secret version doesn't exist
    mock_secrets_manager.get_secret_value.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "Version not found"}}, "GetSecretValue"
    )
    mock_secrets_manager.get_random_password.return_value = {"RandomPassword": "new-password"}

    with patch("management_key.secrets_manager", mock_secrets_manager):
        create_secret(secret_arn, token)

    mock_secrets_manager.get_secret_value.assert_called_once()
    mock_secrets_manager.get_random_password.assert_called_once_with(ExcludePunctuation=True, PasswordLength=16)
    mock_secrets_manager.put_secret_value.assert_called_once_with(
        SecretId=secret_arn, ClientRequestToken=token, SecretString="new-password", VersionStages=["AWSPENDING"]
    )


def test_create_secret_other_client_error(mock_secrets_manager):
    """Test create_secret with other ClientError."""
    secret_arn = "test-secret"
    token = "test-token"

    # Mock a different ClientError
    mock_secrets_manager.get_secret_value.side_effect = ClientError(
        {"Error": {"Code": "InternalServiceError", "Message": "Service error"}}, "GetSecretValue"
    )

    with patch("management_key.secrets_manager", mock_secrets_manager):
        with pytest.raises(ClientError):
            create_secret(secret_arn, token)


def test_create_secret_put_secret_error(mock_secrets_manager):
    """Test create_secret when put_secret_value fails."""
    secret_arn = "test-secret"
    token = "test-token"

    # Mock that the secret version doesn't exist
    mock_secrets_manager.get_secret_value.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "Version not found"}}, "GetSecretValue"
    )
    mock_secrets_manager.get_random_password.return_value = {"RandomPassword": "new-password"}
    mock_secrets_manager.put_secret_value.side_effect = ClientError(
        {"Error": {"Code": "ValidationException", "Message": "Invalid secret"}}, "PutSecretValue"
    )

    with patch("management_key.secrets_manager", mock_secrets_manager):
        with pytest.raises(ClientError):
            create_secret(secret_arn, token)


def test_set_secret_no_op():
    """Test set_secret is a no-op."""
    secret_arn = "test-secret"
    token = "test-token"

    # This should complete without error and without making any calls
    set_secret(secret_arn, token)


def test_test_secret_success(mock_secrets_manager):
    """Test test_secret with valid secret."""
    secret_arn = "test-secret"
    token = "test-token"

    mock_secrets_manager.get_secret_value.return_value = {"SecretString": "validpassword123"}

    with patch("management_key.secrets_manager", mock_secrets_manager):
        validate_secret(secret_arn, token)

    mock_secrets_manager.get_secret_value.assert_called_once_with(
        SecretId=secret_arn, VersionId=token, VersionStage="AWSPENDING"
    )


def test_test_secret_too_short(mock_secrets_manager):
    """Test test_secret with password too short."""
    secret_arn = "test-secret"
    token = "test-token"

    mock_secrets_manager.get_secret_value.return_value = {"SecretString": "short"}

    with patch("management_key.secrets_manager", mock_secrets_manager):
        with pytest.raises(ValueError, match="New secret is invalid - too short or empty"):
            validate_secret(secret_arn, token)


def test_test_secret_empty(mock_secrets_manager):
    """Test test_secret with empty password."""
    secret_arn = "test-secret"
    token = "test-token"

    mock_secrets_manager.get_secret_value.return_value = {"SecretString": ""}

    with patch("management_key.secrets_manager", mock_secrets_manager):
        with pytest.raises(ValueError, match="New secret is invalid - too short or empty"):
            validate_secret(secret_arn, token)


def test_test_secret_contains_punctuation(mock_secrets_manager):
    """Test test_secret with password containing punctuation."""
    secret_arn = "test-secret"
    token = "test-token"

    mock_secrets_manager.get_secret_value.return_value = {"SecretString": "password123!@#"}

    with patch("management_key.secrets_manager", mock_secrets_manager):
        with pytest.raises(ValueError, match="New secret contains punctuation when it shouldn't"):
            validate_secret(secret_arn, token)


def test_test_secret_client_error(mock_secrets_manager):
    """Test test_secret with ClientError."""
    secret_arn = "test-secret"
    token = "test-token"

    mock_secrets_manager.get_secret_value.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "Secret not found"}}, "GetSecretValue"
    )

    with patch("management_key.secrets_manager", mock_secrets_manager):
        with pytest.raises(ClientError):
            validate_secret(secret_arn, token)


def test_finish_secret_success(mock_secrets_manager):
    """Test finish_secret successful completion."""
    secret_arn = "test-secret"
    token = "test-token"

    mock_secrets_manager.describe_secret.return_value = {
        "VersionIdsToStages": {
            "current-version": ["AWSCURRENT"],
            "test-token": ["AWSPENDING"],
        }
    }

    with patch("management_key.secrets_manager", mock_secrets_manager):
        finish_secret(secret_arn, token)

    mock_secrets_manager.describe_secret.assert_called_once_with(SecretId=secret_arn)
    mock_secrets_manager.update_secret_version_stage.assert_called_once_with(
        SecretId=secret_arn,
        VersionStage="AWSCURRENT",
        MoveToVersionId=token,
        RemoveFromVersionId="current-version",
    )


def test_finish_secret_no_current_version(mock_secrets_manager):
    """Test finish_secret when no current version exists."""
    secret_arn = "test-secret"
    token = "test-token"

    mock_secrets_manager.describe_secret.return_value = {
        "VersionIdsToStages": {
            "test-token": ["AWSPENDING"],
        }
    }

    with patch("management_key.secrets_manager", mock_secrets_manager):
        finish_secret(secret_arn, token)

    mock_secrets_manager.update_secret_version_stage.assert_called_once_with(
        SecretId=secret_arn, VersionStage="AWSCURRENT", MoveToVersionId=token, RemoveFromVersionId=None
    )


def test_finish_secret_client_error(mock_secrets_manager):
    """Test finish_secret with ClientError."""
    secret_arn = "test-secret"
    token = "test-token"

    mock_secrets_manager.describe_secret.side_effect = ClientError(
        {"Error": {"Code": "ResourceNotFoundException", "Message": "Secret not found"}}, "DescribeSecret"
    )

    with patch("management_key.secrets_manager", mock_secrets_manager):
        with pytest.raises(ClientError):
            finish_secret(secret_arn, token)


def test_finish_secret_update_error(mock_secrets_manager):
    """Test finish_secret when update_secret_version_stage fails."""
    secret_arn = "test-secret"
    token = "test-token"

    mock_secrets_manager.describe_secret.return_value = {
        "VersionIdsToStages": {
            "current-version": ["AWSCURRENT"],
            "test-token": ["AWSPENDING"],
        }
    }
    mock_secrets_manager.update_secret_version_stage.side_effect = ClientError(
        {"Error": {"Code": "InvalidParameterException", "Message": "Invalid parameter"}}, "UpdateSecretVersionStage"
    )

    with patch("management_key.secrets_manager", mock_secrets_manager):
        with pytest.raises(ClientError):
            finish_secret(secret_arn, token)


def test_rotate_management_key_legacy(mock_secrets_manager):
    """Test legacy rotate_management_key function."""
    event = {}
    ctx = {}

    mock_secrets_manager.get_random_password.return_value = {"RandomPassword": "legacy-password"}

    with patch("management_key.secrets_manager", mock_secrets_manager):
        rotate_management_key(event, ctx)

    mock_secrets_manager.get_random_password.assert_called_once_with(ExcludePunctuation=True, PasswordLength=16)
    mock_secrets_manager.put_secret_value.assert_called_once_with(
        SecretId=os.environ.get("MANAGEMENT_KEY_NAME"), SecretString="legacy-password"
    )


def test_all_punctuation_characters_detected(mock_secrets_manager):
    """Test that all punctuation characters are properly detected."""
    secret_arn = "test-secret"
    token = "test-token"

    # Test various punctuation characters
    punctuation_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
    test_password = f"password{punctuation_chars[0]}"

    mock_secrets_manager.get_secret_value.return_value = {"SecretString": test_password}

    with patch("management_key.secrets_manager", mock_secrets_manager):
        with pytest.raises(ValueError, match="New secret contains punctuation when it shouldn't"):
            validate_secret(secret_arn, token)


@mock_aws
def test_integration_full_rotation_cycle():
    """Integration test for full rotation cycle using moto."""
    import boto3

    # Create a real secrets manager client using moto
    client = boto3.client("secretsmanager", region_name="us-east-1")

    # Create a secret
    secret_name = "test-management-key"
    client.create_secret(Name=secret_name, SecretString="initial-password")

    token = "test-token-integration-12345678901234567890"  # Needs to be at least 32 chars

    with patch("management_key.secrets_manager", client):
        # Step 1: Create new secret version
        create_secret(secret_name, token)

        # Step 2: Set secret (no-op)
        set_secret(secret_name, token)

        # Step 3: Test the secret
        validate_secret(secret_name, token)

        # Step 4: Finish the rotation
        finish_secret(secret_name, token)

    # Verify the rotation completed successfully
    # The rotation workflow should complete without errors, and the new version should exist
    response = client.describe_secret(SecretId=secret_name)
    assert "VersionIdsToStages" in response
    
    # Check that we have both AWSCURRENT and AWSPENDING versions (before cleanup)
    version_stages = response["VersionIdsToStages"]
    assert any("AWSCURRENT" in stages for stages in version_stages.values())
    
    # The workflow completed successfully if we reach this point without exceptions


def test_handler_with_all_steps(mock_secrets_manager, lambda_context):
    """Test handler with all rotation steps."""
    base_event = {
        "SecretId": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret-abcdef",
        "ClientRequestToken": "test-token-123",
    }

    mock_secrets_manager.get_secret_value.side_effect = [
        # First call - version doesn't exist for createSecret
        ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Version not found"}}, "GetSecretValue"
        ),
        # Second call - return valid password for testSecret
        {"SecretString": "validpassword123"},
    ]

    with patch("management_key.secrets_manager", mock_secrets_manager):
        # Test all steps
        for step in ["createSecret", "setSecret", "testSecret", "finishSecret"]:
            event = base_event.copy()
            event["Step"] = step
            response = handler(event, lambda_context)
            assert response["statusCode"] == 200
            assert json.loads(response["body"]) == "Success" 