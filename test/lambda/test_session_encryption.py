#!/usr/bin/env python3
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
Comprehensive tests for session encryption utilities.

This test module provides comprehensive coverage for all functions in
lambda/utilities/session_encryption.py, including error conditions,
edge cases, and exception handling paths.
"""

import base64
import json
import os
import sys
import unittest
from decimal import Decimal
from unittest.mock import patch

# Add the lambda directory to the path so we can import the utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambda"))

from utilities.session_encryption import (
    _create_encryption_context,
    _decrypt_data_key,
    _deserialize_with_type_preservation,
    _generate_data_key,
    _get_kms_key_arn,
    _serialize_with_type_preservation,
    decrypt_session_data,
    decrypt_session_fields,
    encrypt_session_data,
    is_encrypted_data,
    migrate_session_to_encrypted,
    SessionEncryptionError,
    TypePreservingJSONEncoder,
)


class TestSessionEncryption(unittest.TestCase):
    """Test session encryption utilities."""

    def setUp(self):
        """Set up test fixtures."""
        # Set up environment variables
        os.environ["SESSION_ENCRYPTION_KEY_ARN"] = "arn:aws:kms:us-east-1:123456789012:key/test-key-id"
        os.environ["AWS_REGION"] = "us-east-1"

        # Mock KMS client to avoid actual AWS calls
        self.kms_patcher = patch("utilities.session_encryption.kms_client")
        self.mock_kms = self.kms_patcher.start()

        # Mock KMS responses
        self.mock_kms.generate_data_key.return_value = {
            "Plaintext": b"01234567890123456789012345678901",  # 32 bytes
            "CiphertextBlob": b"encrypted_key_data",
        }
        self.mock_kms.decrypt.return_value = {"Plaintext": b"01234567890123456789012345678901"}

        # Test data
        self.test_data = {
            "configuration": {"model": "test-model", "temperature": 0.7},
            "history": [{"type": "human", "content": "Hello"}],
        }
        self.user_id = "test-user"
        self.session_id = "test-session"

    def tearDown(self):
        """Clean up after tests."""
        self.kms_patcher.stop()

    def test_type_preserving_json_encoder_decimal(self):
        """Test TypePreservingJSONEncoder with Decimal objects."""
        encoder = TypePreservingJSONEncoder()
        decimal_value = Decimal("0.01")
        result = encoder.default(decimal_value)
        self.assertIsInstance(result, float)
        self.assertEqual(result, 0.01)

    def test_type_preserving_json_encoder_other_types(self):
        """Test TypePreservingJSONEncoder with other types."""
        encoder = TypePreservingJSONEncoder()

        # Test with a non-Decimal type that would trigger default (like a custom object)
        class CustomObject:
            def __init__(self, value):
                self.value = value

        custom_obj = CustomObject("test")
        # This should raise TypeError since it's not JSON serializable
        with self.assertRaises(TypeError):
            encoder.default(custom_obj)

    def test_serialize_with_type_preservation(self):
        """Test _serialize_with_type_preservation function."""
        data = {"value": Decimal("0.01"), "string": "test"}
        result = _serialize_with_type_preservation(data)
        parsed = json.loads(result)
        self.assertIsInstance(parsed["value"], float)
        self.assertEqual(parsed["value"], 0.01)

    def test_deserialize_with_type_preservation(self):
        """Test _deserialize_with_type_preservation function."""
        json_str = '{"value": 0.01, "count": 42}'
        result = _deserialize_with_type_preservation(json_str)
        self.assertIsInstance(result["value"], float)
        self.assertIsInstance(result["count"], int)

    def test_get_kms_key_arn_success(self):
        """Test _get_kms_key_arn with valid environment variable."""
        result = _get_kms_key_arn()
        self.assertEqual(result, "arn:aws:kms:us-east-1:123456789012:key/test-key-id")

    def test_get_kms_key_arn_missing(self):
        """Test _get_kms_key_arn with missing environment variable."""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SessionEncryptionError) as context:
                _get_kms_key_arn()
            self.assert_in("SESSION_ENCRYPTION_KEY_ARN environment variable not set", str(context.exception))

    def test_get_kms_key_arn_empty(self):
        """Test _get_kms_key_arn with empty environment variable."""
        with patch.dict(os.environ, {"SESSION_ENCRYPTION_KEY_ARN": ""}):
            with self.assertRaises(SessionEncryptionError) as context:
                _get_kms_key_arn()
            self.assert_in("SESSION_ENCRYPTION_KEY_ARN environment variable not set", str(context.exception))

    def test_generate_data_key_success(self):
        """Test _generate_data_key with successful KMS call."""
        key_arn = "arn:aws:kms:us-east-1:123456789012:key/test-key-id"
        encryption_context = {"userId": "test-user", "sessionId": "test-session"}

        plaintext, encrypted = _generate_data_key(key_arn, encryption_context)

        self.assertEqual(plaintext, b"01234567890123456789012345678901")
        self.assertEqual(encrypted, b"encrypted_key_data")
        self.mock_kms.generate_data_key.assert_called_once_with(
            KeyId=key_arn, KeySpec="AES_256", EncryptionContext=encryption_context
        )

    def test_generate_data_key_no_context(self):
        """Test _generate_data_key without encryption context."""
        key_arn = "arn:aws:kms:us-east-1:123456789012:key/test-key-id"

        plaintext, encrypted = _generate_data_key(key_arn)

        self.assertEqual(plaintext, b"01234567890123456789012345678901")
        self.assertEqual(encrypted, b"encrypted_key_data")
        self.mock_kms.generate_data_key.assert_called_once_with(KeyId=key_arn, KeySpec="AES_256", EncryptionContext={})

    def test_generate_data_key_client_error(self):
        """Test _generate_data_key with KMS ClientError."""
        from botocore.exceptions import ClientError

        self.mock_kms.generate_data_key.side_effect = ClientError(
            error_response={"Error": {"Code": "AccessDeniedException"}}, operation_name="GenerateDataKey"
        )

        with self.assertRaises(SessionEncryptionError) as context:
            _generate_data_key("arn:aws:kms:us-east-1:123456789012:key/test-key-id")

        self.assert_in("Failed to generate data key", str(context.exception))

    def test_decrypt_data_key_success(self):
        """Test _decrypt_data_key with successful KMS call."""
        encrypted_key = b"encrypted_key_data"
        encryption_context = {"userId": "test-user", "sessionId": "test-session"}

        result = _decrypt_data_key(encrypted_key, encryption_context)

        self.assertEqual(result, b"01234567890123456789012345678901")
        self.mock_kms.decrypt.assert_called_once_with(
            CiphertextBlob=encrypted_key, EncryptionContext=encryption_context
        )

    def test_decrypt_data_key_no_context(self):
        """Test _decrypt_data_key without encryption context."""
        encrypted_key = b"encrypted_key_data"

        result = _decrypt_data_key(encrypted_key)

        self.assertEqual(result, b"01234567890123456789012345678901")
        self.mock_kms.decrypt.assert_called_once_with(CiphertextBlob=encrypted_key, EncryptionContext={})

    def test_decrypt_data_key_client_error(self):
        """Test _decrypt_data_key with KMS ClientError."""
        from botocore.exceptions import ClientError

        self.mock_kms.decrypt.side_effect = ClientError(
            error_response={"Error": {"Code": "AccessDeniedException"}}, operation_name="Decrypt"
        )

        with self.assertRaises(SessionEncryptionError) as context:
            _decrypt_data_key(b"encrypted_key_data")

        self.assert_in("Failed to decrypt data key", str(context.exception))

    def test_create_encryption_context(self):
        """Test _create_encryption_context function."""
        result = _create_encryption_context("user123", "session456")
        expected = {"userId": "user123", "sessionId": "session456", "purpose": "session-encryption"}
        self.assertEqual(result, expected)

    def test_encrypt_session_data_success(self):
        """Test encrypt_session_data with successful encryption."""
        result = encrypt_session_data(self.test_data, self.user_id, self.session_id)

        # Verify result is a base64 encoded string
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

        # Verify it can be decoded
        decoded = base64.b64decode(result).decode("utf-8")
        parsed = json.loads(decoded)
        self.assert_in("encrypted_key", parsed)
        self.assert_in("encrypted_data", parsed)
        self.assert_in("encryption_version", parsed)

    def test_encrypt_session_data_exception(self):
        """Test encrypt_session_data with exception during encryption."""
        # Mock KMS to raise an exception
        self.mock_kms.generate_data_key.side_effect = Exception("KMS error")

        with self.assertRaises(SessionEncryptionError) as context:
            encrypt_session_data(self.test_data, self.user_id, self.session_id)

        self.assert_in("Failed to encrypt session data", str(context.exception))

    def test_decrypt_session_data_success(self):
        """Test decrypt_session_data with successful decryption."""
        # First encrypt some data
        encrypted_data = encrypt_session_data(self.test_data, self.user_id, self.session_id)

        # Then decrypt it
        result = decrypt_session_data(encrypted_data, self.user_id, self.session_id)

        # Verify the decrypted data matches the original
        self.assertEqual(result, self.test_data)

    def test_decrypt_session_data_exception(self):
        """Test decrypt_session_data with exception during decryption."""
        # Create invalid encrypted data
        invalid_data = "invalid_base64_data"

        with self.assertRaises(SessionEncryptionError) as context:
            decrypt_session_data(invalid_data, self.user_id, self.session_id)

        self.assert_in("Failed to decrypt session data", str(context.exception))

    def test_is_encrypted_data_valid(self):
        """Test is_encrypted_data with valid encrypted data."""
        # Create valid encrypted data structure
        valid_data = {
            "encrypted_key": "key_data",
            "encrypted_data": "data_data",
            "encryption_version": "1.0",
        }
        encoded_data = base64.b64encode(json.dumps(valid_data).encode("utf-8")).decode("utf-8")

        result = is_encrypted_data(encoded_data)
        self.assertTrue(result)

    def test_is_encrypted_data_invalid_structure(self):
        """Test is_encrypted_data with invalid structure."""
        # Create data with missing fields
        invalid_data = {"encrypted_key": "key_data"}  # Missing required fields
        encoded_data = base64.b64encode(json.dumps(invalid_data).encode("utf-8")).decode("utf-8")

        result = is_encrypted_data(encoded_data)
        self.assertFalse(result)

    def test_is_encrypted_data_invalid_json(self):
        """Test is_encrypted_data with invalid JSON."""
        # Create invalid JSON
        invalid_data = "not_valid_json"
        encoded_data = base64.b64encode(invalid_data.encode("utf-8")).decode("utf-8")

        result = is_encrypted_data(encoded_data)
        self.assertFalse(result)

    def test_is_encrypted_data_invalid_base64(self):
        """Test is_encrypted_data with invalid base64."""
        # Create invalid base64
        invalid_data = "not_valid_base64!"

        result = is_encrypted_data(invalid_data)
        self.assertFalse(result)

    def test_is_encrypted_data_non_dict(self):
        """Test is_encrypted_data with non-dict JSON."""
        # Create valid JSON but not a dict
        invalid_data = ["not", "a", "dict"]
        encoded_data = base64.b64encode(json.dumps(invalid_data).encode("utf-8")).decode("utf-8")

        result = is_encrypted_data(encoded_data)
        self.assertFalse(result)

    def test_migrate_session_to_encrypted_success(self):
        """Test migrate_session_to_encrypted with successful migration."""
        session_data = {
            "sessionId": "test-session",
            "history": [{"type": "human", "content": "Hello"}],
            "configuration": {"model": "test-model"},
            "other_field": "value",
        }

        result = migrate_session_to_encrypted(session_data, self.user_id, self.session_id)

        # Verify encryption metadata
        self.assertTrue(result["is_encrypted"])
        self.assertEqual(result["encryption_version"], "1.0")

        # Verify fields were encrypted
        self.assert_in("encrypted_history", result)
        self.assert_in("encrypted_configuration", result)

        # Verify original fields were removed
        self.assertNotIn("history", result)
        self.assertNotIn("configuration", result)

        # Verify other fields remain
        self.assertEqual(result["sessionId"], "test-session")
        self.assertEqual(result["other_field"], "value")

    def test_migrate_session_to_encrypted_missing_fields(self):
        """Test migrate_session_to_encrypted with missing fields to encrypt."""
        session_data = {
            "sessionId": "test-session",
            "other_field": "value",
        }

        result = migrate_session_to_encrypted(session_data, self.user_id, self.session_id)

        # Verify encryption metadata
        self.assertTrue(result["is_encrypted"])
        self.assertEqual(result["encryption_version"], "1.0")

        # Verify no encrypted fields were added
        self.assertNotIn("encrypted_history", result)
        self.assertNotIn("encrypted_configuration", result)

    def test_migrate_session_to_encrypted_none_fields(self):
        """Test migrate_session_to_encrypted with None fields."""
        session_data = {
            "sessionId": "test-session",
            "history": None,
            "configuration": None,
        }

        result = migrate_session_to_encrypted(session_data, self.user_id, self.session_id)

        # Verify encryption metadata
        self.assertTrue(result["is_encrypted"])
        self.assertEqual(result["encryption_version"], "1.0")

        # Verify no encrypted fields were added for None values
        self.assertNotIn("encrypted_history", result)
        self.assertNotIn("encrypted_configuration", result)

    def test_migrate_session_to_encrypted_exception(self):
        """Test migrate_session_to_encrypted with exception during encryption."""
        # Mock encrypt_session_data to raise an exception
        with patch("utilities.session_encryption.encrypt_session_data") as mock_encrypt:
            mock_encrypt.side_effect = Exception("Encryption error")

            session_data = {
                "sessionId": "test-session",
                "history": [{"type": "human", "content": "Hello"}],
            }

            with self.assertRaises(SessionEncryptionError) as context:
                migrate_session_to_encrypted(session_data, self.user_id, self.session_id)

            self.assert_in("Failed to migrate session to encrypted", str(context.exception))

    def test_decrypt_session_fields_success(self):
        """Test decrypt_session_fields with successful decryption."""
        # Create encrypted session data
        encrypted_session = {
            "sessionId": "test-session",
            "encrypted_history": "encrypted_history_data",
            "encrypted_configuration": "encrypted_config_data",
            "is_encrypted": True,
            "encryption_version": "1.0",
        }

        # Mock decrypt_session_data to return decrypted data
        with patch("utilities.session_encryption.decrypt_session_data") as mock_decrypt:
            mock_decrypt.side_effect = [
                [{"type": "human", "content": "Hello"}],  # history
                {"model": "test-model"},  # configuration
            ]

            result = decrypt_session_fields(encrypted_session, self.user_id, self.session_id)

            # Verify decrypted fields
            self.assertEqual(result["history"], [{"type": "human", "content": "Hello"}])
            self.assertEqual(result["configuration"], {"model": "test-model"})

            # Verify encrypted fields were removed
            self.assertNotIn("encrypted_history", result)
            self.assertNotIn("encrypted_configuration", result)

            # Verify metadata was removed
            self.assertNotIn("is_encrypted", result)
            self.assertNotIn("encryption_version", result)

            # Verify other fields remain
            self.assertEqual(result["sessionId"], "test-session")

    def test_decrypt_session_fields_missing_fields(self):
        """Test decrypt_session_fields with missing encrypted fields."""
        session_data = {
            "sessionId": "test-session",
            "other_field": "value",
        }

        result = decrypt_session_fields(session_data, self.user_id, self.session_id)

        # Verify no changes were made
        self.assertEqual(result, session_data)

    def test_decrypt_session_fields_none_fields(self):
        """Test decrypt_session_fields with None encrypted fields."""
        session_data = {
            "sessionId": "test-session",
            "encrypted_history": None,
            "encrypted_configuration": None,
        }

        result = decrypt_session_fields(session_data, self.user_id, self.session_id)

        # Verify no changes were made
        self.assertEqual(result, session_data)

    def test_decrypt_session_fields_exception(self):
        """Test decrypt_session_fields with exception during decryption."""
        # Mock decrypt_session_data to raise an exception
        with patch("utilities.session_encryption.decrypt_session_data") as mock_decrypt:
            mock_decrypt.side_effect = Exception("Decryption error")

            session_data = {
                "sessionId": "test-session",
                "encrypted_history": "encrypted_data",
            }

            with self.assertRaises(SessionEncryptionError) as context:
                decrypt_session_fields(session_data, self.user_id, self.session_id)

            self.assert_in("Failed to decrypt session fields", str(context.exception))

    def test_end_to_end_encryption_decryption(self):
        """Test complete encryption and decryption cycle."""
        # Test data with various types
        test_data = {
            "configuration": {
                "model": "test-model",
                "temperature": 0.7,
                "max_tokens": 1000,
                "enabled": True,
            },
            "history": [
                {"type": "human", "content": "Hello"},
                {"type": "assistant", "content": "Hi there!"},
            ],
            "metadata": {"version": 1, "score": 0.95},
        }

        # Encrypt the data
        encrypted_data = encrypt_session_data(test_data, self.user_id, self.session_id)

        # Verify it's encrypted
        self.assertTrue(is_encrypted_data(encrypted_data))

        # Decrypt the data
        decrypted_data = decrypt_session_data(encrypted_data, self.user_id, self.session_id)

        # Verify the data matches
        self.assertEqual(decrypted_data, test_data)

    def test_migrate_and_decrypt_cycle(self):
        """Test complete migration and decryption cycle."""
        # Original session data
        session_data = {
            "sessionId": "test-session",
            "userId": "test-user",
            "history": [{"type": "human", "content": "Hello"}],
            "configuration": {"model": "test-model"},
            "other_field": "value",
        }

        # Migrate to encrypted
        encrypted_session = migrate_session_to_encrypted(session_data, self.user_id, self.session_id)

        # Verify encryption metadata
        self.assertTrue(encrypted_session["is_encrypted"])
        self.assertEqual(encrypted_session["encryption_version"], "1.0")

        # Decrypt the fields
        decrypted_session = decrypt_session_fields(encrypted_session, self.user_id, self.session_id)

        # Verify the decrypted session matches the original (minus encryption metadata)
        expected_session = session_data.copy()
        self.assertEqual(decrypted_session["sessionId"], expected_session["sessionId"])
        self.assertEqual(decrypted_session["userId"], expected_session["userId"])
        self.assertEqual(decrypted_session["other_field"], expected_session["other_field"])

    def test_edge_case_empty_data(self):
        """Test encryption/decryption with empty data."""
        empty_data = {}

        encrypted_data = encrypt_session_data(empty_data, self.user_id, self.session_id)
        decrypted_data = decrypt_session_data(encrypted_data, self.user_id, self.session_id)

        self.assertEqual(decrypted_data, empty_data)

    def test_edge_case_none_values(self):
        """Test encryption/decryption with None values."""
        data_with_none = {"value": None, "nested": {"key": None}}

        encrypted_data = encrypt_session_data(data_with_none, self.user_id, self.session_id)
        decrypted_data = decrypt_session_data(encrypted_data, self.user_id, self.session_id)

        self.assertEqual(decrypted_data, data_with_none)

    def test_edge_case_large_data(self):
        """Test encryption/decryption with large data."""
        large_data = {
            "large_string": "x" * 10000,
            "large_list": list(range(1000)),
            "nested": {"deep": {"structure": {"with": {"many": {"levels": "value"}}}}},
        }

        encrypted_data = encrypt_session_data(large_data, self.user_id, self.session_id)
        decrypted_data = decrypt_session_data(encrypted_data, self.user_id, self.session_id)

        self.assertEqual(decrypted_data, large_data)


if __name__ == "__main__":
    # Set up environment variables for testing
    os.environ["AWS_REGION"] = "us-east-1"
    os.environ["SESSION_ENCRYPTION_KEY_ARN"] = "arn:aws:kms:us-east-1:123456789012:key/test-key-id"

    # Run the tests
    unittest.main(verbosity=2)
