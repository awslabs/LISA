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

"""Unit tests for session encryption functionality."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from moto import mock_aws

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["SESSION_ENCRYPTION_KEY_ARN"] = "arn:aws:kms:us-east-1:123456789012:key/12345678-1234-1234-1234-123456789012"
os.environ["SESSION_ENCRYPTION_ENABLED"] = "true"


@pytest.fixture(scope="function")
def mock_kms():
    """Mock KMS client."""
    with mock_aws():
        import boto3

        kms_client = boto3.client("kms", region_name="us-east-1")

        # Create a mock KMS key
        key_response = kms_client.create_key(
            Description="Test session encryption key", KeyUsage="ENCRYPT_DECRYPT", KeySpec="SYMMETRIC_DEFAULT"
        )

        yield kms_client, key_response["KeyMetadata"]["KeyId"]


@pytest.fixture(scope="function")
def mock_event():
    """Mock API Gateway event."""
    return {
        "httpMethod": "POST",
        "path": "/session/encryption/generate-key",
        "headers": {"Authorization": "Bearer test-token"},
        "body": json.dumps({"sessionId": "test-session-123", "userId": "test-user-456"}),
        "requestContext": {"authorizer": {"claims": {"cognito:username": "test-user-456"}}},
    }


@pytest.fixture(scope="function")
def mock_context():
    """Mock Lambda context."""
    context = MagicMock()
    context.function_name = "test-function"
    context.memory_limit_in_mb = 128
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789012:function:test-function"
    context.aws_request_id = "test-request-id"
    return context


class TestSessionEncryption:
    """Test cases for session encryption functionality."""

    def setup_method(self):
        """Set up test isolation."""
        # Store reference to current api_wrapper for debugging
        import utilities.common_functions

        self.current_api_wrapper = utilities.common_functions.api_wrapper

    def _assert_response_structure(self, result, expected_status_code):
        """Helper to assert response structure regardless of api_wrapper behavior."""
        # Check if we're using the real api_wrapper (always returns 200) or mocked one
        if result["statusCode"] == 200:
            # Real api_wrapper - check nested structure
            outer_body = json.loads(result["body"])
            assert outer_body["statusCode"] == expected_status_code
            inner_body = json.loads(outer_body["body"])
            assert "error" in inner_body
        else:
            # Mocked api_wrapper - direct status code, error in body as JSON string
            assert result["statusCode"] == expected_status_code
            body = json.loads(result["body"])
            assert "error" in body

    def test_encrypt_session_data_success(self, mock_kms):
        """Test successful session data encryption."""
        from utilities.session_encryption import encrypt_session_data

        kms_client, key_id = mock_kms

        # Mock the KMS generate_data_key response
        with patch("utilities.session_encryption.kms_client") as mock_kms_client:
            mock_kms_client.generate_data_key.return_value = {
                "Plaintext": b"test-plaintext-key-32-bytes-long",
                "CiphertextBlob": b"encrypted-key-blob",
            }

            # Test data
            test_data = {"messages": [{"type": "human", "content": "Hello"}]}
            user_id = "test-user"
            session_id = "test-session"

            # Encrypt the data
            encrypted_data = encrypt_session_data(test_data, user_id, session_id)

            # Verify the result
            assert encrypted_data is not None
            assert isinstance(encrypted_data, str)

            # Verify the structure
            import base64

            decoded = base64.b64decode(encrypted_data).decode("utf-8")
            parsed = json.loads(decoded)

            assert "encrypted_key" in parsed
            assert "encrypted_data" in parsed
            assert "encryption_version" in parsed
            assert parsed["encryption_version"] == "1.0"

    def test_decrypt_session_data_success(self, mock_kms):
        """Test successful session data decryption."""
        from utilities.session_encryption import decrypt_session_data, encrypt_session_data

        kms_client, key_id = mock_kms

        # Mock KMS responses
        with patch("utilities.session_encryption.kms_client") as mock_kms_client:
            mock_kms_client.generate_data_key.return_value = {
                "Plaintext": b"test-plaintext-key-32-bytes-long",
                "CiphertextBlob": b"encrypted-key-blob",
            }
            mock_kms_client.decrypt.return_value = {"Plaintext": b"test-plaintext-key-32-bytes-long"}

            # Test data
            test_data = {"messages": [{"type": "human", "content": "Hello"}]}
            user_id = "test-user"
            session_id = "test-session"

            # Encrypt the data
            encrypted_data = encrypt_session_data(test_data, user_id, session_id)

            # Decrypt the data
            decrypted_data = decrypt_session_data(encrypted_data, user_id, session_id)

            # Verify the result
            assert decrypted_data == test_data

    def test_is_encrypted_data_detection(self):
        """Test encrypted data detection."""
        from utilities.session_encryption import is_encrypted_data

        # Test with encrypted data structure
        encrypted_data = {"encrypted_key": "test-key", "encrypted_data": "test-data", "encryption_version": "1.0"}

        import base64

        encrypted_string = base64.b64encode(json.dumps(encrypted_data).encode("utf-8")).decode("utf-8")

        assert is_encrypted_data(encrypted_string) is True

        # Test with non-encrypted data
        plain_data = "This is plain text"
        assert is_encrypted_data(plain_data) is False

    def test_migrate_session_to_encrypted(self, mock_kms):
        """Test session migration to encrypted format."""
        from utilities.session_encryption import migrate_session_to_encrypted

        kms_client, key_id = mock_kms

        # Mock KMS response
        with patch("utilities.session_encryption.kms_client") as mock_kms_client:
            mock_kms_client.generate_data_key.return_value = {
                "Plaintext": b"test-plaintext-key-32-bytes-long",
                "CiphertextBlob": b"encrypted-key-blob",
            }

            # Test session data
            session_data = {
                "history": [{"type": "human", "content": "Hello"}],
                "configuration": {"model": "gpt-4"},
                "name": "Test Session",
                "startTime": "2024-01-01T00:00:00Z",
            }

            user_id = "test-user"
            session_id = "test-session"

            # Migrate to encrypted
            encrypted_session = migrate_session_to_encrypted(session_data, user_id, session_id)

            # Verify the result
            assert "encrypted_history" in encrypted_session
            assert "encrypted_configuration" in encrypted_session
            assert "encryption_version" in encrypted_session
            assert "is_encrypted" in encrypted_session
            assert encrypted_session["is_encrypted"] is True
            assert encrypted_session["encryption_version"] == "1.0"

            # Verify original fields are removed
            assert "history" not in encrypted_session
            assert "configuration" not in encrypted_session

    def test_decrypt_session_fields(self, mock_kms):
        """Test decryption of session fields."""
        from utilities.session_encryption import decrypt_session_fields, migrate_session_to_encrypted

        kms_client, key_id = mock_kms

        # Mock KMS responses
        with patch("utilities.session_encryption.kms_client") as mock_kms_client:
            mock_kms_client.generate_data_key.return_value = {
                "Plaintext": b"test-plaintext-key-32-bytes-long",
                "CiphertextBlob": b"encrypted-key-blob",
            }
            mock_kms_client.decrypt.return_value = {"Plaintext": b"test-plaintext-key-32-bytes-long"}

            # Test session data
            session_data = {
                "history": [{"type": "human", "content": "Hello"}],
                "configuration": {"model": "gpt-4"},
                "name": "Test Session",
            }

            user_id = "test-user"
            session_id = "test-session"

            # Migrate to encrypted
            encrypted_session = migrate_session_to_encrypted(session_data, user_id, session_id)

            # Decrypt the fields
            decrypted_session = decrypt_session_fields(encrypted_session, user_id, session_id)

            # Verify the result
            assert "history" in decrypted_session
            assert "configuration" in decrypted_session
            assert decrypted_session["history"] == session_data["history"]
            assert decrypted_session["configuration"] == session_data["configuration"]

            # Verify encrypted fields are removed
            assert "encrypted_history" not in decrypted_session
            assert "encrypted_configuration" not in decrypted_session
            assert "encryption_version" not in decrypted_session
            assert "is_encrypted" not in decrypted_session

    def test_encryption_error_handling(self):
        """Test encryption error handling."""
        from utilities.session_encryption import encrypt_session_data, SessionEncryptionError

        # Test with missing KMS key ARN
        with patch.dict(os.environ, {"SESSION_ENCRYPTION_KEY_ARN": ""}):
            with pytest.raises(SessionEncryptionError):
                encrypt_session_data({"test": "data"}, "user", "session")

    def test_encrypt_session_data_kms_error(self, mock_kms):
        """Test encryption with KMS error."""
        from utilities.session_encryption import encrypt_session_data

        kms_client, key_id = mock_kms

        # Mock KMS error
        with patch("utilities.session_encryption.kms_client") as mock_kms_client:
            mock_kms_client.generate_data_key.side_effect = Exception("KMS error")

            test_data = {"messages": [{"type": "human", "content": "Hello"}]}
            user_id = "test-user"
            session_id = "test-session"

            with pytest.raises(Exception):
                encrypt_session_data(test_data, user_id, session_id)

    def test_decrypt_session_data_kms_error(self, mock_kms):
        """Test decryption with KMS error."""
        from utilities.session_encryption import decrypt_session_data, encrypt_session_data

        kms_client, key_id = mock_kms

        # First encrypt some data
        with patch("utilities.session_encryption.kms_client") as mock_kms_client:
            mock_kms_client.generate_data_key.return_value = {
                "Plaintext": b"test-plaintext-key-32-bytes-long",
                "CiphertextBlob": b"encrypted-key-blob",
            }

            test_data = {"messages": [{"type": "human", "content": "Hello"}]}
            user_id = "test-user"
            session_id = "test-session"

            encrypted_data = encrypt_session_data(test_data, user_id, session_id)

            # Now test decryption with KMS error
            mock_kms_client.decrypt.side_effect = Exception("KMS error")

            with pytest.raises(Exception):
                decrypt_session_data(encrypted_data, user_id, session_id)

    def test_migrate_session_to_encrypted_kms_error(self, mock_kms):
        """Test migration with KMS error."""
        from utilities.session_encryption import migrate_session_to_encrypted

        kms_client, key_id = mock_kms

        # Mock KMS error
        with patch("utilities.session_encryption.kms_client") as mock_kms_client:
            mock_kms_client.generate_data_key.side_effect = Exception("KMS error")

            session_data = {
                "history": [{"type": "human", "content": "Hello"}],
                "configuration": {"model": "gpt-4"},
                "name": "Test Session",
            }

            user_id = "test-user"
            session_id = "test-session"

            with pytest.raises(Exception):
                migrate_session_to_encrypted(session_data, user_id, session_id)

    def test_decrypt_session_fields_kms_error(self, mock_kms):
        """Test decrypt session fields with KMS error."""
        from utilities.session_encryption import decrypt_session_fields, migrate_session_to_encrypted

        kms_client, key_id = mock_kms

        # First create encrypted session
        with patch("utilities.session_encryption.kms_client") as mock_kms_client:
            mock_kms_client.generate_data_key.return_value = {
                "Plaintext": b"test-plaintext-key-32-bytes-long",
                "CiphertextBlob": b"encrypted-key-blob",
            }

            session_data = {
                "history": [{"type": "human", "content": "Hello"}],
                "configuration": {"model": "gpt-4"},
                "name": "Test Session",
            }

            user_id = "test-user"
            session_id = "test-session"

            encrypted_session = migrate_session_to_encrypted(session_data, user_id, session_id)

            # Now test decryption with KMS error
            mock_kms_client.decrypt.side_effect = Exception("KMS error")

            with pytest.raises(Exception):
                decrypt_session_fields(encrypted_session, user_id, session_id)

    def test_generate_data_key_lambda(self, mock_event, mock_context):
        """Test generate data key Lambda function."""
        from session.encryption_lambda_functions import generate_data_key

        with patch("session.encryption_lambda_functions.kms_client") as mock_kms_client:
            mock_kms_client.generate_data_key.return_value = {
                "Plaintext": b"test-plaintext-key-32-bytes-long",
                "CiphertextBlob": b"encrypted-key-blob",
            }

            # Mock the get_username function
            with patch("session.encryption_lambda_functions.get_username") as mock_get_username:
                mock_get_username.return_value = "test-user-456"

                # Call the function
                result = generate_data_key(mock_event, mock_context)

                # Verify the result
                assert result["statusCode"] == 200
                # The api_wrapper returns the response in the body field as JSON string
                # Parse the nested JSON structure
                outer_body = json.loads(result["body"])
                if "body" in outer_body:
                    inner_body = json.loads(outer_body["body"])
                    assert "plaintext" in inner_body
                    assert "encrypted" in inner_body
                else:
                    # Direct response structure
                    assert "plaintext" in outer_body
                    assert "encrypted" in outer_body

    def test_decrypt_data_key_lambda(self, mock_event, mock_context):
        """Test decrypt data key Lambda function."""
        from session.encryption_lambda_functions import decrypt_data_key

        # Update event for decrypt operation
        mock_event["body"] = json.dumps({"encryptedKey": "dGVzdC1lbmNyeXB0ZWQta2V5", "sessionId": "test-session-123"})

        with patch("session.encryption_lambda_functions.kms_client") as mock_kms_client:
            mock_kms_client.decrypt.return_value = {"Plaintext": b"test-plaintext-key-32-bytes-long"}

            # Mock the get_username function
            with patch("session.encryption_lambda_functions.get_username") as mock_get_username:
                mock_get_username.return_value = "test-user-456"

                # Call the function
                result = decrypt_data_key(mock_event, mock_context)

                # Verify the result
                assert result["statusCode"] == 200
                # The api_wrapper returns the response in the body field as JSON string
                # Parse the nested JSON structure
                outer_body = json.loads(result["body"])
                if "body" in outer_body:
                    inner_body = json.loads(outer_body["body"])
                    assert "plaintext" in inner_body
                else:
                    # Direct response structure
                    assert "plaintext" in outer_body

    def test_get_encryption_config_lambda(self, mock_event, mock_context):
        """Test get encryption config Lambda function."""
        from session.encryption_lambda_functions import get_encryption_config

        # Update event for GET operation
        mock_event["httpMethod"] = "GET"
        mock_event["path"] = "/session/encryption/config"
        mock_event["body"] = None

        # Mock the get_username function
        with patch("session.encryption_lambda_functions.get_username") as mock_get_username:
            mock_get_username.return_value = "test-user-456"

            # Call the function
            result = get_encryption_config(mock_event, mock_context)

            # Verify the result
            assert result["statusCode"] == 200
            # The api_wrapper returns the response in the body field as JSON string
            # Parse the nested JSON structure
            outer_body = json.loads(result["body"])
            if "body" in outer_body:
                inner_body = json.loads(outer_body["body"])
                assert "enabled" in inner_body
                assert "kmsKeyArn" in inner_body
                assert "userId" in inner_body
                assert inner_body["userId"] == "test-user-456"
            else:
                # Direct response structure
                assert "enabled" in outer_body
                assert "kmsKeyArn" in outer_body
                assert "userId" in outer_body
                assert outer_body["userId"] == "test-user-456"

    def test_generate_data_key_lambda_missing_session_id(self, mock_event, mock_context):
        """Test generate data key Lambda function with missing session ID."""
        from session.encryption_lambda_functions import generate_data_key

        # Update event with missing sessionId
        mock_event["body"] = json.dumps({"userId": "test-user-456"})

        # Mock the get_username function
        with patch("session.encryption_lambda_functions.get_username") as mock_get_username:
            mock_get_username.return_value = "test-user-456"

            # Call the function
            result = generate_data_key(mock_event, mock_context)

            # Verify the result - handle both real and mocked api_wrapper behavior
            self._assert_response_structure(result, 400)

    def test_generate_data_key_lambda_invalid_json(self, mock_event, mock_context):
        """Test generate data key Lambda function with invalid JSON."""
        from session.encryption_lambda_functions import generate_data_key

        # Update event with invalid JSON
        mock_event["body"] = "invalid json"

        # Mock the get_username function
        with patch("session.encryption_lambda_functions.get_username") as mock_get_username:
            mock_get_username.return_value = "test-user-456"

            # Call the function
            result = generate_data_key(mock_event, mock_context)

            # Verify the result - handle both real and mocked api_wrapper behavior
            self._assert_response_structure(result, 400)

    def test_generate_data_key_lambda_kms_error(self, mock_event, mock_context):
        """Test generate data key Lambda function with KMS error."""
        from session.encryption_lambda_functions import generate_data_key

        with patch("session.encryption_lambda_functions.kms_client") as mock_kms_client:
            mock_kms_client.generate_data_key.side_effect = Exception("KMS error")

            # Mock the get_username function
            with patch("session.encryption_lambda_functions.get_username") as mock_get_username:
                mock_get_username.return_value = "test-user-456"

                # Call the function
                result = generate_data_key(mock_event, mock_context)

                # Verify the result - handle both real and mocked api_wrapper behavior
                self._assert_response_structure(result, 500)

    def test_decrypt_data_key_lambda_missing_encrypted_key(self, mock_event, mock_context):
        """Test decrypt data key Lambda function with missing encrypted key."""
        from session.encryption_lambda_functions import decrypt_data_key

        # Update event with missing encryptedKey
        mock_event["body"] = json.dumps({"sessionId": "test-session-123"})

        # Mock the get_username function
        with patch("session.encryption_lambda_functions.get_username") as mock_get_username:
            mock_get_username.return_value = "test-user-456"

            # Call the function
            result = decrypt_data_key(mock_event, mock_context)

            # Verify the result - handle both real and mocked api_wrapper behavior
            self._assert_response_structure(result, 400)

    def test_decrypt_data_key_lambda_kms_error(self, mock_event, mock_context):
        """Test decrypt data key Lambda function with KMS error."""
        from session.encryption_lambda_functions import decrypt_data_key

        # Update event for decrypt operation
        mock_event["body"] = json.dumps({"encryptedKey": "dGVzdC1lbmNyeXB0ZWQta2V5", "sessionId": "test-session-123"})

        with patch("session.encryption_lambda_functions.kms_client") as mock_kms_client:
            mock_kms_client.decrypt.side_effect = Exception("KMS error")

            # Mock the get_username function
            with patch("session.encryption_lambda_functions.get_username") as mock_get_username:
                mock_get_username.return_value = "test-user-456"

                # Call the function
                result = decrypt_data_key(mock_event, mock_context)

                # Verify the result - handle both real and mocked api_wrapper behavior
                self._assert_response_structure(result, 500)

    def test_update_encryption_config_lambda(self, mock_event, mock_context):
        """Test update encryption config Lambda function."""
        from session.encryption_lambda_functions import update_encryption_config

        # Update event for PUT operation
        mock_event["httpMethod"] = "PUT"
        mock_event["path"] = "/session/encryption/config"
        mock_event["body"] = json.dumps({"enabled": True})

        # Mock the get_username function
        with patch("session.encryption_lambda_functions.get_username") as mock_get_username:
            mock_get_username.return_value = "test-user-456"

            # Call the function
            result = update_encryption_config(mock_event, mock_context)

            # Verify the result
            assert result["statusCode"] == 200
            outer_body = json.loads(result["body"])
            if "body" in outer_body:
                inner_body = json.loads(outer_body["body"])
                assert "message" in inner_body
                assert inner_body["enabled"] is True
            else:
                assert "message" in outer_body
                assert outer_body["enabled"] is True

    def test_update_encryption_config_lambda_invalid_json(self, mock_event, mock_context):
        """Test update encryption config Lambda function with invalid JSON."""
        from session.encryption_lambda_functions import update_encryption_config

        # Update event for PUT operation with invalid JSON
        mock_event["httpMethod"] = "PUT"
        mock_event["path"] = "/session/encryption/config"
        mock_event["body"] = "invalid json"

        # Mock the get_username function
        with patch("session.encryption_lambda_functions.get_username") as mock_get_username:
            mock_get_username.return_value = "test-user-456"

            # Call the function
            result = update_encryption_config(mock_event, mock_context)

            # Verify the result - handle both real and mocked api_wrapper behavior
            self._assert_response_structure(result, 400)

    def test_numeric_type_preservation_serialization(self):
        """Test that numeric types are preserved through JSON serialization/deserialization."""
        from utilities.session_encryption import _deserialize_with_type_preservation, _serialize_with_type_preservation

        # Test data with various numeric types that should be preserved
        test_data = {
            "configuration": {
                "selectedModel": {
                    "top_p": 0.01,  # This should remain a float
                    "temperature": 0.7,  # This should remain a float
                    "max_tokens": 1000,  # This should remain an int
                    "presence_penalty": -0.1,  # This should remain a float
                }
            },
            "history": [{"type": "human", "content": "Test message"}],
        }

        # Serialize the data
        json_str = _serialize_with_type_preservation(test_data)

        # Deserialize the data
        deserialized_data = _deserialize_with_type_preservation(json_str)

        # Verify that numeric types are preserved
        assert isinstance(deserialized_data["configuration"]["selectedModel"]["top_p"], float)
        assert deserialized_data["configuration"]["selectedModel"]["top_p"] == 0.01

        assert isinstance(deserialized_data["configuration"]["selectedModel"]["temperature"], float)
        assert deserialized_data["configuration"]["selectedModel"]["temperature"] == 0.7

        assert isinstance(deserialized_data["configuration"]["selectedModel"]["max_tokens"], int)
        assert deserialized_data["configuration"]["selectedModel"]["max_tokens"] == 1000

        assert isinstance(deserialized_data["configuration"]["selectedModel"]["presence_penalty"], float)
        assert deserialized_data["configuration"]["selectedModel"]["presence_penalty"] == -0.1

        # Verify the entire structure is preserved
        assert deserialized_data == test_data
