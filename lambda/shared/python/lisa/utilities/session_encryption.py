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

"""Utilities for encrypting and decrypting session data."""

import base64
import json
import logging
import os
from decimal import Decimal
from typing import Any

import boto3
from botocore.exceptions import ClientError
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

# Initialize KMS client
kms_client = boto3.client("kms", region_name=os.environ.get("AWS_REGION", "us-east-1"))


class TypePreservingJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that preserves numeric types."""

    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


def _serialize_with_type_preservation(data: Any) -> str:
    """Serialize data to JSON while preserving numeric types."""
    return json.dumps(data, cls=TypePreservingJSONEncoder)


def _deserialize_with_type_preservation(json_str: str) -> Any:
    """Deserialize JSON string while preserving numeric types."""
    return json.loads(json_str, parse_float=float, parse_int=int)


class SessionEncryptionError(Exception):
    """Custom exception for session encryption errors."""

    pass


def _get_kms_key_arn() -> str:
    """Get the KMS key ARN from environment variables."""
    key_arn = os.environ.get("SESSION_ENCRYPTION_KEY_ARN")
    if not key_arn:
        raise SessionEncryptionError("SESSION_ENCRYPTION_KEY_ARN environment variable not set")
    return key_arn


def _generate_data_key(key_arn: str, encryption_context: dict[str, str] | None = None) -> tuple[bytes, bytes]:
    """
    Generate a data key from KMS.

    Args:
        key_arn: KMS key ARN
        encryption_context: Optional encryption context

    Returns:
        Tuple of (plaintext_data_key, encrypted_data_key)
    """
    try:
        response = kms_client.generate_data_key(
            KeyId=key_arn, KeySpec="AES_256", EncryptionContext=encryption_context or {}
        )
        return response["Plaintext"], response["CiphertextBlob"]
    except ClientError as e:
        logger.error(f"Failed to generate data key: {e}")
        raise SessionEncryptionError(f"Failed to generate data key: {e}")


def _decrypt_data_key(encrypted_data_key: bytes, encryption_context: dict[str, str] | None = None) -> bytes:
    """
    Decrypt a data key using KMS.

    Args:
        encrypted_data_key: Encrypted data key
        encryption_context: Optional encryption context

    Returns:
        Plaintext data key
    """
    try:
        response = kms_client.decrypt(CiphertextBlob=encrypted_data_key, EncryptionContext=encryption_context or {})
        return response["Plaintext"]  # type: ignore
    except ClientError as e:
        logger.error(f"Failed to decrypt data key: {e}")
        raise SessionEncryptionError(f"Failed to decrypt data key: {e}")


def _create_encryption_context(user_id: str, session_id: str) -> dict[str, str]:
    """
    Create encryption context for KMS operations.

    Args:
        user_id: User ID
        session_id: Session ID

    Returns:
        Encryption context dictionary
    """
    return {"userId": user_id, "sessionId": session_id, "purpose": "session-encryption"}


def encrypt_session_data(data: Any, user_id: str, session_id: str) -> str:
    """
    Encrypt session data using KMS envelope encryption.

    Args:
        data: Data to encrypt (will be JSON serialized)
        user_id: User ID for encryption context
        session_id: Session ID for encryption context

    Returns:
        Base64 encoded string containing encrypted data key and encrypted data
    """
    try:
        # Create encryption context
        encryption_context = _create_encryption_context(user_id, session_id)

        # Get KMS key ARN
        key_arn = _get_kms_key_arn()

        # Generate data key
        plaintext_key, encrypted_key = _generate_data_key(key_arn, encryption_context)

        # Serialize data to JSON while preserving numeric types
        json_data = _serialize_with_type_preservation(data)

        # Encrypt data using Fernet (AES 128 in CBC mode with PKCS7 padding)
        fernet = Fernet(base64.urlsafe_b64encode(plaintext_key[:32]))
        encrypted_data = fernet.encrypt(json_data.encode("utf-8"))

        # Combine encrypted key and encrypted data
        combined = {
            "encrypted_key": base64.b64encode(encrypted_key).decode("utf-8"),
            "encrypted_data": base64.b64encode(encrypted_data).decode("utf-8"),
            "encryption_version": "1.0",
        }

        return base64.b64encode(json.dumps(combined).encode("utf-8")).decode("utf-8")

    except Exception as e:
        logger.error(f"Failed to encrypt session data: {e}")
        raise SessionEncryptionError(f"Failed to encrypt session data: {e}")


def decrypt_session_data(encrypted_data: str, user_id: str, session_id: str) -> Any:
    """
    Decrypt session data using KMS envelope encryption.

    Args:
        encrypted_data: Base64 encoded encrypted data
        user_id: User ID for encryption context
        session_id: Session ID for encryption context

    Returns:
        Decrypted and deserialized data
    """
    try:
        # Create encryption context
        encryption_context = _create_encryption_context(user_id, session_id)

        # Decode the combined data
        combined_json = base64.b64decode(encrypted_data).decode("utf-8")
        combined = json.loads(combined_json)

        # Extract encrypted key and data
        encrypted_key = base64.b64decode(combined["encrypted_key"])
        encrypted_data_bytes = base64.b64decode(combined["encrypted_data"])

        # Decrypt the data key
        plaintext_key = _decrypt_data_key(encrypted_key, encryption_context)

        # Decrypt the data
        fernet = Fernet(base64.urlsafe_b64encode(plaintext_key[:32]))
        decrypted_json = fernet.decrypt(encrypted_data_bytes).decode("utf-8")

        # Deserialize and return while preserving numeric types
        return _deserialize_with_type_preservation(decrypted_json)

    except Exception as e:
        logger.error(f"Failed to decrypt session data: {e}")
        raise SessionEncryptionError(f"Failed to decrypt session data: {e}")


def is_encrypted_data(data: str) -> bool:
    """
    Check if a string appears to be encrypted session data.

    Args:
        data: String to check

    Returns:
        True if data appears to be encrypted
    """
    try:
        # Try to decode as base64
        decoded = base64.b64decode(data).decode("utf-8")
        parsed = json.loads(decoded)

        # Check if it has the expected structure
        return (
            isinstance(parsed, dict)
            and "encrypted_key" in parsed
            and "encrypted_data" in parsed
            and "encryption_version" in parsed
        )
    except Exception:
        return False


def migrate_session_to_encrypted(session_data: dict[str, Any], user_id: str, session_id: str) -> dict[str, Any]:
    """
    Migrate a session from unencrypted to encrypted format.

    Args:
        session_data: Session data dictionary
        user_id: User ID
        session_id: Session ID

    Returns:
        Updated session data with encrypted fields
    """
    try:
        # Fields to encrypt
        fields_to_encrypt = ["history", "configuration"]

        # Create a copy of the session data
        encrypted_session = session_data.copy()

        # Encrypt sensitive fields
        for field in fields_to_encrypt:
            if field in session_data and session_data[field] is not None:
                encrypted_value = encrypt_session_data(session_data[field], user_id, session_id)
                encrypted_session[f"encrypted_{field}"] = encrypted_value
                # Remove the unencrypted field
                del encrypted_session[field]

        # Add encryption metadata
        encrypted_session["encryption_version"] = "1.0"
        encrypted_session["is_encrypted"] = True

        return encrypted_session

    except Exception as e:
        logger.error(f"Failed to migrate session to encrypted: {e}")
        raise SessionEncryptionError(f"Failed to migrate session to encrypted: {e}")


def decrypt_session_fields(session_data: dict[str, Any], user_id: str, session_id: str) -> dict[str, Any]:
    """
    Decrypt encrypted fields in session data.

    Args:
        session_data: Session data dictionary
        user_id: User ID
        session_id: Session ID

    Returns:
        Session data with decrypted fields
    """
    try:
        # Fields that might be encrypted
        encrypted_fields = ["encrypted_history", "encrypted_configuration"]
        decrypted_session = session_data.copy()

        # Decrypt encrypted fields
        for encrypted_field in encrypted_fields:
            if encrypted_field in session_data and session_data[encrypted_field] is not None:
                # Get the original field name
                original_field = encrypted_field.replace("encrypted_", "")

                # Decrypt the data
                decrypted_data = decrypt_session_data(session_data[encrypted_field], user_id, session_id)
                decrypted_session[original_field] = decrypted_data

                # Remove the encrypted field
                del decrypted_session[encrypted_field]

        # Remove encryption metadata
        decrypted_session.pop("encryption_version", None)
        decrypted_session.pop("is_encrypted", None)

        return decrypted_session

    except Exception as e:
        logger.error(f"Failed to decrypt session fields: {e}")
        raise SessionEncryptionError(f"Failed to decrypt session fields: {e}")
