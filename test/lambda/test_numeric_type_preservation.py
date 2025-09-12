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
Unit test to verify numeric type preservation through encryption/decryption.

This test ensures that numeric types (floats, ints) are preserved correctly
when session data goes through the encryption/decryption process.
"""

import json
import os
import sys
import unittest
from decimal import Decimal
from unittest.mock import patch

# Add the lambda directory to the path so we can import the utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "lambda"))

from utilities.session_encryption import (
    _deserialize_with_type_preservation,
    _serialize_with_type_preservation,
    decrypt_session_data,
    encrypt_session_data,
    TypePreservingJSONEncoder,
)


class TestNumericTypePreservation(unittest.TestCase):
    """Test numeric type preservation through encryption/decryption."""

    def setUp(self):
        """Set up test fixtures."""
        # Set up environment variables
        os.environ["SESSION_ENCRYPTION_KEY_ARN"] = "arn:aws:kms:us-east-1:123456789012:key/test-key-id"

        # Mock KMS client to avoid actual AWS calls
        self.kms_patcher = patch("utilities.session_encryption.kms_client")
        self.mock_kms = self.kms_patcher.start()

        # Mock KMS responses
        self.mock_kms.generate_data_key.return_value = {
            "Plaintext": b"01234567890123456789012345678901",  # 32 bytes
            "CiphertextBlob": b"encrypted_key_data",
        }
        self.mock_kms.decrypt.return_value = {"Plaintext": b"01234567890123456789012345678901"}

        # Test data with various numeric types
        self.test_session_data = {
            "configuration": {
                "selectedModel": {
                    "top_p": 0.01,  # float
                    "temperature": 0.7,  # float
                    "max_tokens": 1000,  # int
                    "presence_penalty": -0.1,  # negative float
                    "frequency_penalty": 0.0,  # zero float
                    "stop_sequences": ["</s>", "<|endoftext|>"],  # non-numeric
                    "model_id": "gpt-4",  # string
                    "enabled": True,  # boolean
                }
            },
            "history": [
                {"type": "human", "content": "Test message with numbers: 42 and 3.14"},
                {"type": "assistant", "content": "Response with numeric values: 100 and 0.5"},
            ],
            "metadata": {
                "session_id": "test-session-123",
                "version": 1,  # int
                "score": 0.95,  # float
                "count": 0,  # zero int
            },
        }

    def tearDown(self):
        """Clean up after tests."""
        self.kms_patcher.stop()

    def test_type_preserving_json_encoder(self):
        """Test that TypePreservingJSONEncoder preserves numeric types."""
        encoder = TypePreservingJSONEncoder()

        # Test with Decimal (should convert to float)
        decimal_value = Decimal("0.01")
        result = encoder.default(decimal_value)
        self.assertIsInstance(result, float)
        self.assertEqual(result, 0.01)

        # Test with other types (should use default behavior)
        # Note: int, str, bool are already JSON serializable, so they won't call default()
        # We can test this by encoding a full object
        test_data = {"int": 42, "float": 3.14, "decimal": Decimal("0.01")}
        json_str = json.dumps(test_data, cls=TypePreservingJSONEncoder)
        parsed = json.loads(json_str)

        self.assertIsInstance(parsed["int"], int)
        self.assertIsInstance(parsed["float"], float)
        self.assertIsInstance(parsed["decimal"], float)  # Decimal converted to float

    def test_serialize_deserialize_preservation(self):
        """Test that serialize/deserialize preserves numeric types."""
        # Serialize the test data
        json_str = _serialize_with_type_preservation(self.test_session_data)

        # Deserialize the data
        deserialized_data = _deserialize_with_type_preservation(json_str)

        # Verify numeric types are preserved
        config = deserialized_data["configuration"]["selectedModel"]

        # Check float types
        self.assertIsInstance(config["top_p"], float)
        self.assertEqual(config["top_p"], 0.01)

        self.assertIsInstance(config["temperature"], float)
        self.assertEqual(config["temperature"], 0.7)

        self.assertIsInstance(config["presence_penalty"], float)
        self.assertEqual(config["presence_penalty"], -0.1)

        self.assertIsInstance(config["frequency_penalty"], float)
        self.assertEqual(config["frequency_penalty"], 0.0)

        # Check int types
        self.assertIsInstance(config["max_tokens"], int)
        self.assertEqual(config["max_tokens"], 1000)

        # Check metadata numeric types
        metadata = deserialized_data["metadata"]
        self.assertIsInstance(metadata["version"], int)
        self.assertEqual(metadata["version"], 1)

        self.assertIsInstance(metadata["score"], float)
        self.assertEqual(metadata["score"], 0.95)

        self.assertIsInstance(metadata["count"], int)
        self.assertEqual(metadata["count"], 0)

        # Verify non-numeric types are unchanged
        self.assertIsInstance(config["stop_sequences"], list)
        self.assertIsInstance(config["model_id"], str)
        self.assertIsInstance(config["enabled"], bool)

    def test_encryption_decryption_preservation(self):
        """Test that encryption/decryption preserves numeric types."""
        user_id = "test-user-123"
        session_id = "test-session-456"

        # Encrypt the session data
        encrypted_data = encrypt_session_data(self.test_session_data, user_id, session_id)

        # Verify encryption produced a string
        self.assertIsInstance(encrypted_data, str)
        self.assertGreater(len(encrypted_data), 0)

        # Decrypt the session data
        decrypted_data = decrypt_session_data(encrypted_data, user_id, session_id)

        # Verify the decrypted data structure matches original
        self.assertEqual(decrypted_data["configuration"]["selectedModel"]["top_p"], 0.01)
        self.assertEqual(decrypted_data["configuration"]["selectedModel"]["temperature"], 0.7)
        self.assertEqual(decrypted_data["configuration"]["selectedModel"]["max_tokens"], 1000)
        self.assertEqual(decrypted_data["configuration"]["selectedModel"]["presence_penalty"], -0.1)
        self.assertEqual(decrypted_data["configuration"]["selectedModel"]["frequency_penalty"], 0.0)

        # Verify numeric types are preserved after encryption/decryption
        config = decrypted_data["configuration"]["selectedModel"]

        # Check float types
        self.assertIsInstance(config["top_p"], float)
        self.assertIsInstance(config["temperature"], float)
        self.assertIsInstance(config["presence_penalty"], float)
        self.assertIsInstance(config["frequency_penalty"], float)

        # Check int types
        self.assertIsInstance(config["max_tokens"], int)

        # Check metadata numeric types
        metadata = decrypted_data["metadata"]
        self.assertIsInstance(metadata["version"], int)
        self.assertIsInstance(metadata["score"], float)
        self.assertIsInstance(metadata["count"], int)

        # Verify the entire structure is preserved
        self.assertEqual(decrypted_data, self.test_session_data)

    def test_edge_cases(self):
        """Test edge cases for numeric type preservation."""
        edge_case_data = {
            "very_small_float": 1e-10,
            "very_large_float": 1e10,
            "negative_int": -42,
            "zero_float": 0.0,
            "zero_int": 0,
            "negative_float": -3.14159,
            "nested_numbers": {"level1": {"level2": {"value": 0.123456789}}},
            "array_with_numbers": [1, 2.5, -3, 0.0, 1000],
            "mixed_array": ["string", 42, 0.5, True, None],
        }

        user_id = "test-user-edge"
        session_id = "test-session-edge"

        # Encrypt and decrypt
        encrypted = encrypt_session_data(edge_case_data, user_id, session_id)
        decrypted = decrypt_session_data(encrypted, user_id, session_id)

        # Verify numeric types are preserved
        self.assertIsInstance(decrypted["very_small_float"], float)
        self.assertEqual(decrypted["very_small_float"], 1e-10)

        self.assertIsInstance(decrypted["very_large_float"], float)
        self.assertEqual(decrypted["very_large_float"], 1e10)

        self.assertIsInstance(decrypted["negative_int"], int)
        self.assertEqual(decrypted["negative_int"], -42)

        self.assertIsInstance(decrypted["zero_float"], float)
        self.assertEqual(decrypted["zero_float"], 0.0)

        self.assertIsInstance(decrypted["zero_int"], int)
        self.assertEqual(decrypted["zero_int"], 0)

        self.assertIsInstance(decrypted["negative_float"], float)
        self.assertEqual(decrypted["negative_float"], -3.14159)

        # Check nested numeric types
        nested_value = decrypted["nested_numbers"]["level1"]["level2"]["value"]
        self.assertIsInstance(nested_value, float)
        self.assertEqual(nested_value, 0.123456789)

        # Check array numeric types
        array = decrypted["array_with_numbers"]
        self.assertIsInstance(array[0], int)  # 1
        self.assertIsInstance(array[1], float)  # 2.5
        self.assertIsInstance(array[2], int)  # -3
        self.assertIsInstance(array[3], float)  # 0.0
        self.assertIsInstance(array[4], int)  # 1000

    def test_json_parsing_with_correct_types(self):
        """Test that JSON parsing with float/int preserves types correctly."""
        # Simulate the JSON parsing that happens in Lambda functions
        json_data = {
            "configuration": {
                "selectedModel": {"top_p": 0.01, "temperature": 0.7, "max_tokens": 1000, "presence_penalty": -0.1}
            }
        }

        # Convert to JSON string and parse back (simulating Lambda behavior)
        json_str = json.dumps(json_data)
        parsed_data = json.loads(json_str, parse_float=float, parse_int=int)

        # Verify types are correct
        config = parsed_data["configuration"]["selectedModel"]
        self.assertIsInstance(config["top_p"], float)
        self.assertIsInstance(config["temperature"], float)
        self.assertIsInstance(config["max_tokens"], int)
        self.assertIsInstance(config["presence_penalty"], float)

        # Now test encryption/decryption with this correctly parsed data
        user_id = "test-user-json"
        session_id = "test-session-json"

        encrypted = encrypt_session_data(parsed_data, user_id, session_id)
        decrypted = decrypt_session_data(encrypted, user_id, session_id)

        # Verify types are still correct after encryption/decryption
        decrypted_config = decrypted["configuration"]["selectedModel"]
        self.assertIsInstance(decrypted_config["top_p"], float)
        self.assertIsInstance(decrypted_config["temperature"], float)
        self.assertIsInstance(decrypted_config["max_tokens"], int)
        self.assertIsInstance(decrypted_config["presence_penalty"], float)

        # Verify values are correct
        self.assertEqual(decrypted_config["top_p"], 0.01)
        self.assertEqual(decrypted_config["temperature"], 0.7)
        self.assertEqual(decrypted_config["max_tokens"], 1000)
        self.assertEqual(decrypted_config["presence_penalty"], -0.1)


if __name__ == "__main__":
    # Set up environment variables for testing
    os.environ["AWS_REGION"] = "us-east-1"
    os.environ["SESSION_ENCRYPTION_KMS_KEY_ARN"] = "arn:aws:kms:us-east-1:123456789012:key/test-key-id"

    # Run the tests
    unittest.main(verbosity=2)
