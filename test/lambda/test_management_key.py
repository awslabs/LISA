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
Refactored management key tests using fixture-based mocking instead of global mocks.
This replaces the original test_management_key.py with isolated, maintainable tests.
"""

import json
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
        "MANAGEMENT_KEY_NAME": "test-management-key",
    }

    for key, value in env_vars.items():
        os.environ[key] = value

    yield

    # Cleanup
    for key in env_vars.keys():
        if key in os.environ:
            del os.environ[key]


@pytest.fixture
def management_key_functions():
    """Import management key functions."""
    import os
    import sys

    # Add lambda directory to path
    lambda_dir = os.path.join(os.path.dirname(__file__), "../../lambda")
    if lambda_dir not in sys.path:
        sys.path.insert(0, lambda_dir)

    import management_key

    return management_key


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


class TestHandler:
    """Test handler function - REFACTORED VERSION."""

    def test_handler_create_secret_success(
        self, sample_event, lambda_context, mock_secrets_manager, management_key_functions
    ):
        """Test successful createSecret step."""
        # Mock that the secret version doesn't exist
        mock_secrets_manager.get_secret_value.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Version not found"}}, "GetSecretValue"
        )

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            response = management_key_functions.handler(sample_event, lambda_context)

        assert response["statusCode"] == 200
        assert json.loads(response["body"]) == "Success"
        mock_secrets_manager.get_secret_value.assert_called_once()
        mock_secrets_manager.get_random_password.assert_called_once()
        mock_secrets_manager.put_secret_value.assert_called_once()

    def test_handler_create_secret_success_step1_format(
        self, sample_event_step1, lambda_context, mock_secrets_manager, management_key_functions
    ):
        """Test successful createSecret step with Step1 format."""
        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            response = management_key_functions.handler(sample_event_step1, lambda_context)

        assert response["statusCode"] == 200
        assert json.loads(response["body"]) == "Success"

    def test_handler_set_secret_success(
        self, sample_event, lambda_context, mock_secrets_manager, management_key_functions
    ):
        """Test successful setSecret step."""
        sample_event["Step"] = "setSecret"

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            response = management_key_functions.handler(sample_event, lambda_context)

        assert response["statusCode"] == 200
        assert json.loads(response["body"]) == "Success"

    def test_handler_test_secret_success(
        self, sample_event, lambda_context, mock_secrets_manager, management_key_functions
    ):
        """Test successful testSecret step."""
        sample_event["Step"] = "testSecret"
        mock_secrets_manager.get_secret_value.return_value = {"SecretString": "testpassword16chars"}

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            response = management_key_functions.handler(sample_event, lambda_context)

        assert response["statusCode"] == 200
        assert json.loads(response["body"]) == "Success"

    def test_handler_finish_secret_success(
        self, sample_event, lambda_context, mock_secrets_manager, management_key_functions
    ):
        """Test successful finishSecret step."""
        sample_event["Step"] = "finishSecret"

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            response = management_key_functions.handler(sample_event, lambda_context)

        assert response["statusCode"] == 200
        assert json.loads(response["body"]) == "Success"

    def test_handler_missing_secret_id(self, lambda_context, management_key_functions):
        """Test handler with missing SecretId."""
        event = {"ClientRequestToken": "test-token-123", "Step": "createSecret"}

        with pytest.raises(ValueError, match="SecretId and ClientRequestToken are required"):
            management_key_functions.handler(event, lambda_context)

    def test_handler_missing_token(self, lambda_context, management_key_functions):
        """Test handler with missing ClientRequestToken."""
        event = {"SecretId": "test-secret", "Step": "createSecret"}

        with pytest.raises(ValueError, match="SecretId and ClientRequestToken are required"):
            management_key_functions.handler(event, lambda_context)

    def test_handler_invalid_step(self, sample_event, lambda_context, management_key_functions):
        """Test handler with invalid step."""
        sample_event["Step"] = "invalidStep"

        with pytest.raises(ValueError, match="Invalid step parameter: invalidStep"):
            management_key_functions.handler(sample_event, lambda_context)

    def test_handler_exception_propagation(
        self, sample_event, lambda_context, mock_secrets_manager, management_key_functions
    ):
        """Test that exceptions are properly propagated from handler."""
        mock_secrets_manager.get_secret_value.side_effect = ClientError(
            {"Error": {"Code": "InternalServiceError", "Message": "Service error"}}, "GetSecretValue"
        )

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            with pytest.raises(ClientError):
                management_key_functions.handler(sample_event, lambda_context)

    def test_handler_with_all_steps(self, mock_secrets_manager, lambda_context, management_key_functions):
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

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            # Test all steps
            for step in ["createSecret", "setSecret", "testSecret", "finishSecret"]:
                event = base_event.copy()
                event["Step"] = step
                response = management_key_functions.handler(event, lambda_context)
                assert response["statusCode"] == 200
                assert json.loads(response["body"]) == "Success"


class TestCreateSecret:
    """Test create_secret function - REFACTORED VERSION."""

    def test_create_secret_already_exists(self, mock_secrets_manager, management_key_functions):
        """Test create_secret when version already exists."""
        secret_arn = "test-secret"
        token = "test-token"

        # Mock that the secret version already exists
        mock_secrets_manager.get_secret_value.return_value = {"SecretString": "existing-password"}

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            management_key_functions.create_secret(secret_arn, token)

        # Should only call get_secret_value, not create new password
        mock_secrets_manager.get_secret_value.assert_called_once_with(
            SecretId=secret_arn, VersionId=token, VersionStage="AWSPENDING"
        )
        mock_secrets_manager.get_random_password.assert_not_called()
        mock_secrets_manager.put_secret_value.assert_not_called()

    def test_create_secret_not_found_creates_new(self, mock_secrets_manager, management_key_functions):
        """Test create_secret when version doesn't exist."""
        secret_arn = "test-secret"
        token = "test-token"

        # Mock that the secret version doesn't exist
        mock_secrets_manager.get_secret_value.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Version not found"}}, "GetSecretValue"
        )
        mock_secrets_manager.get_random_password.return_value = {"RandomPassword": "new-password"}

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            management_key_functions.create_secret(secret_arn, token)

        mock_secrets_manager.get_secret_value.assert_called_once()
        mock_secrets_manager.get_random_password.assert_called_once_with(ExcludePunctuation=True, PasswordLength=16)
        mock_secrets_manager.put_secret_value.assert_called_once_with(
            SecretId=secret_arn, ClientRequestToken=token, SecretString="new-password", VersionStages=["AWSPENDING"]
        )

    def test_create_secret_other_client_error(self, mock_secrets_manager, management_key_functions):
        """Test create_secret with other ClientError."""
        secret_arn = "test-secret"
        token = "test-token"

        # Mock a different ClientError
        mock_secrets_manager.get_secret_value.side_effect = ClientError(
            {"Error": {"Code": "InternalServiceError", "Message": "Service error"}}, "GetSecretValue"
        )

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            with pytest.raises(ClientError):
                management_key_functions.create_secret(secret_arn, token)

    def test_create_secret_put_secret_error(self, mock_secrets_manager, management_key_functions):
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

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            with pytest.raises(ClientError):
                management_key_functions.create_secret(secret_arn, token)


class TestSetSecret:
    """Test set_secret function - REFACTORED VERSION."""

    def test_set_secret_no_op(self, management_key_functions):
        """Test set_secret is a no-op."""
        secret_arn = "test-secret"
        token = "test-token"

        # This should complete without error and without making any calls
        management_key_functions.set_secret(secret_arn, token)


class TestTestSecret:
    """Test test_secret function - REFACTORED VERSION."""

    def test_test_secret_success(self, mock_secrets_manager, management_key_functions):
        """Test test_secret with valid secret."""
        secret_arn = "test-secret"
        token = "test-token"

        mock_secrets_manager.get_secret_value.return_value = {"SecretString": "validpassword123"}

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            management_key_functions.test_secret(secret_arn, token)

        mock_secrets_manager.get_secret_value.assert_called_once_with(
            SecretId=secret_arn, VersionId=token, VersionStage="AWSPENDING"
        )

    def test_test_secret_too_short(self, mock_secrets_manager, management_key_functions):
        """Test test_secret with password too short."""
        secret_arn = "test-secret"
        token = "test-token"

        mock_secrets_manager.get_secret_value.return_value = {"SecretString": "short"}

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            with pytest.raises(ValueError, match="New secret is invalid - too short or empty"):
                management_key_functions.test_secret(secret_arn, token)

    def test_test_secret_empty(self, mock_secrets_manager, management_key_functions):
        """Test test_secret with empty password."""
        secret_arn = "test-secret"
        token = "test-token"

        mock_secrets_manager.get_secret_value.return_value = {"SecretString": ""}

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            with pytest.raises(ValueError, match="New secret is invalid - too short or empty"):
                management_key_functions.test_secret(secret_arn, token)

    def test_test_secret_contains_punctuation(self, mock_secrets_manager, management_key_functions):
        """Test test_secret with password containing punctuation."""
        secret_arn = "test-secret"
        token = "test-token"

        mock_secrets_manager.get_secret_value.return_value = {"SecretString": "password123!@#"}

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            with pytest.raises(ValueError, match="New secret contains punctuation when it shouldn't"):
                management_key_functions.test_secret(secret_arn, token)

    def test_test_secret_client_error(self, mock_secrets_manager, management_key_functions):
        """Test test_secret with ClientError."""
        secret_arn = "test-secret"
        token = "test-token"

        mock_secrets_manager.get_secret_value.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Secret not found"}}, "GetSecretValue"
        )

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            with pytest.raises(ClientError):
                management_key_functions.test_secret(secret_arn, token)

    def test_all_punctuation_characters_detected(self, mock_secrets_manager, management_key_functions):
        """Test that all punctuation characters are properly detected."""
        secret_arn = "test-secret"
        token = "test-token"

        # Test various punctuation characters
        punctuation_chars = "!@#$%^&*()_+-=[]{}|;:,.<>?"
        test_password = f"password{punctuation_chars[0]}"

        mock_secrets_manager.get_secret_value.return_value = {"SecretString": test_password}

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            with pytest.raises(ValueError, match="New secret contains punctuation when it shouldn't"):
                management_key_functions.test_secret(secret_arn, token)


class TestFinishSecret:
    """Test finish_secret function - REFACTORED VERSION."""

    def test_finish_secret_success(self, mock_secrets_manager, management_key_functions):
        """Test finish_secret successful completion."""
        secret_arn = "test-secret"
        token = "test-token"

        mock_secrets_manager.describe_secret.return_value = {
            "VersionIdsToStages": {
                "current-version": ["AWSCURRENT"],
                "test-token": ["AWSPENDING"],
            }
        }

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            management_key_functions.finish_secret(secret_arn, token)

        mock_secrets_manager.describe_secret.assert_called_once_with(SecretId=secret_arn)
        mock_secrets_manager.update_secret_version_stage.assert_called_once_with(
            SecretId=secret_arn,
            VersionStage="AWSCURRENT",
            MoveToVersionId=token,
            RemoveFromVersionId="current-version",
        )

    def test_finish_secret_no_current_version(self, mock_secrets_manager, management_key_functions):
        """Test finish_secret when no current version exists."""
        secret_arn = "test-secret"
        token = "test-token"

        mock_secrets_manager.describe_secret.return_value = {
            "VersionIdsToStages": {
                "test-token": ["AWSPENDING"],
            }
        }

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            management_key_functions.finish_secret(secret_arn, token)

        mock_secrets_manager.update_secret_version_stage.assert_called_once_with(
            SecretId=secret_arn, VersionStage="AWSCURRENT", MoveToVersionId=token, RemoveFromVersionId=None
        )

    def test_finish_secret_client_error(self, mock_secrets_manager, management_key_functions):
        """Test finish_secret with ClientError."""
        secret_arn = "test-secret"
        token = "test-token"

        mock_secrets_manager.describe_secret.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException", "Message": "Secret not found"}}, "DescribeSecret"
        )

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            with pytest.raises(ClientError):
                management_key_functions.finish_secret(secret_arn, token)

    def test_finish_secret_update_error(self, mock_secrets_manager, management_key_functions):
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

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            with pytest.raises(ClientError):
                management_key_functions.finish_secret(secret_arn, token)


class TestRotateManagementKey:
    """Test rotate_management_key legacy function - REFACTORED VERSION."""

    def test_rotate_management_key_legacy(self, mock_secrets_manager, management_key_functions):
        """Test legacy rotate_management_key function."""
        event = {}
        ctx = {}

        mock_secrets_manager.get_random_password.return_value = {"RandomPassword": "legacy-password"}

        with patch.object(management_key_functions, "secrets_manager", mock_secrets_manager):
            management_key_functions.rotate_management_key(event, ctx)

        mock_secrets_manager.get_random_password.assert_called_once_with(ExcludePunctuation=True, PasswordLength=16)
        mock_secrets_manager.put_secret_value.assert_called_once_with(
            SecretId=os.environ.get("MANAGEMENT_KEY_NAME"), SecretString="legacy-password"
        )
