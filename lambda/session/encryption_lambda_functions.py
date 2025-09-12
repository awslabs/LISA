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

"""Lambda functions for session encryption key management."""

import base64
import json
import logging
import os
import time
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError
from utilities.common_functions import api_wrapper, get_username, retry_config

logger = logging.getLogger(__name__)

# Initialize clients
kms_client = boto3.client("kms", region_name=os.environ.get("AWS_REGION", "us-east-1"), config=retry_config)
dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
config_table = dynamodb.Table(os.environ["CONFIG_TABLE_NAME"])

# Cache for configuration values to avoid repeated database queries
_config_cache: Dict[str, Dict[str, Any]] = {}
_cache_ttl = 300  # 5 minutes
_cache_invalidation_timestamp = 0


def _check_cache_invalidation() -> bool:
    """Check if the cache should be invalidated based on SSM parameter.

    Returns
    -------
    bool
        True if cache should be invalidated, False otherwise.
    """
    global _cache_invalidation_timestamp

    try:
        ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)

        try:
            response = ssm_client.get_parameter(Name="/lisa/cache/session-encryption-invalidation")

            invalidation_timestamp = int(response["Parameter"]["Value"])

            # If the invalidation timestamp is newer than our last check, invalidate cache
            if invalidation_timestamp > _cache_invalidation_timestamp:
                logger.info(f"Cache invalidation detected: {invalidation_timestamp} > {_cache_invalidation_timestamp}")
                _cache_invalidation_timestamp = invalidation_timestamp
                return True

        except (ClientError, ValueError) as e:
            # Parameter doesn't exist or invalid format, don't invalidate
            logger.debug(f"No cache invalidation parameter found: {e}")

    except Exception as e:
        logger.warning(f"Error checking cache invalidation: {e}")

    return False


def _is_session_encryption_enabled() -> bool:
    """Check if session encryption is enabled via global configuration.

    Returns
    -------
    bool
        True if session encryption is enabled, False otherwise.
        Defaults to False if configuration is not found or accessible.
    """
    cache_key = "global_config_encryption"
    current_time = time.time()

    # Check if cache should be invalidated
    if _check_cache_invalidation():
        logger.info("Invalidating session encryption cache due to configuration update")
        _config_cache.clear()

    # Check cache first
    if cache_key in _config_cache:
        cached_data = _config_cache[cache_key]
        if current_time - cached_data["timestamp"] < _cache_ttl:
            logger.debug("Using cached global configuration for session encryption")
            return cached_data["value"]  # type: ignore [no-any-return]

    try:
        logger.debug("Querying global configuration for session encryption setting")
        # Query the global configuration entry
        response = config_table.query(
            KeyConditionExpression="configScope = :scope",
            ExpressionAttributeValues={":scope": "global"},
            ScanIndexForward=False,
            Limit=1,
        )

        items = response.get("Items", [])
        if items:
            config_item = items[0]
            configuration = config_item.get("configuration", {})
            enabled_components = configuration.get("enabledComponents", {})
            encrypt_session = enabled_components.get("encryptSession", False)  # Default to False

            # Handle various boolean representations
            if isinstance(encrypt_session, bool):
                result = encrypt_session
            elif isinstance(encrypt_session, str):
                result = encrypt_session.lower() in ("true", "1", "yes", "on")
            elif isinstance(encrypt_session, (int, float)):
                result = bool(encrypt_session)
            else:
                logger.warning(f"Unexpected type for encryptSession: {type(encrypt_session)}, defaulting to False")
                result = False

            # Cache the result
            _config_cache[cache_key] = {"value": result, "timestamp": current_time}

            logger.info(f"Retrieved session encryption setting from global config: {result}")
            return result
        else:
            logger.warning("No global configuration found, defaulting session encryption to disabled")
            # Cache the default value
            _config_cache[cache_key] = {"value": False, "timestamp": current_time}
            return False

    except ClientError as error:
        logger.error(f"Failed to query global configuration: {error}, defaulting to encryption disabled")
        return False
    except Exception as e:
        logger.error(f"Error checking session encryption configuration: {e}, defaulting to disabled")
        return False


@api_wrapper
def generate_data_key(event: dict, context: dict) -> dict:
    """Generate a data key for session encryption."""
    try:
        user_id = get_username(event)

        # Parse request body
        try:
            body = json.loads(event.get("body", "{}"))  # noqa: P103
        except json.JSONDecodeError as e:
            return {"statusCode": 400, "body": json.dumps({"error": f"Invalid JSON: {e}"})}

        session_id = body.get("sessionId")
        if not session_id:
            return {"statusCode": 400, "body": json.dumps({"error": "sessionId is required"})}

        # Get KMS key ARN from environment
        kms_key_arn = os.environ.get("SESSION_ENCRYPTION_KEY_ARN")
        if not kms_key_arn:
            return {"statusCode": 500, "body": json.dumps({"error": "Encryption key not configured"})}

        # Create encryption context
        encryption_context = {"userId": user_id, "sessionId": session_id, "purpose": "session-encryption"}

        # Generate data key
        try:
            response = kms_client.generate_data_key(
                KeyId=kms_key_arn, KeySpec="AES_256", EncryptionContext=encryption_context
            )

            # Return base64 encoded keys
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "plaintext": base64.b64encode(response["Plaintext"]).decode("utf-8"),
                        "encrypted": base64.b64encode(response["CiphertextBlob"]).decode("utf-8"),
                    }
                ),
            }
        except ClientError as e:
            logger.error(f"Failed to generate data key: {e}")
            return {"statusCode": 500, "body": json.dumps({"error": "Failed to generate encryption key"})}

    except Exception as e:
        logger.error(f"Error in generate_data_key: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error"})}


@api_wrapper
def decrypt_data_key(event: dict, context: dict) -> dict:
    """Decrypt a data key for session decryption."""
    try:
        user_id = get_username(event)

        # Parse request body
        try:
            body = json.loads(event.get("body", "{}"))  # noqa: P103
        except json.JSONDecodeError as e:
            return {"statusCode": 400, "body": json.dumps({"error": f"Invalid JSON: {e}"})}

        encrypted_key = body.get("encryptedKey")
        session_id = body.get("sessionId")

        if not encrypted_key or not session_id:
            return {"statusCode": 400, "body": json.dumps({"error": "encryptedKey and sessionId are required"})}

        # Create encryption context
        encryption_context = {"userId": user_id, "sessionId": session_id, "purpose": "session-encryption"}

        # Decrypt the data key
        try:
            response = kms_client.decrypt(
                CiphertextBlob=base64.b64decode(encrypted_key), EncryptionContext=encryption_context
            )

            # Return base64 encoded plaintext key
            return {
                "statusCode": 200,
                "body": json.dumps({"plaintext": base64.b64encode(response["Plaintext"]).decode("utf-8")}),
            }
        except ClientError as e:
            logger.error(f"Failed to decrypt data key: {e}")
            return {"statusCode": 500, "body": json.dumps({"error": "Failed to decrypt encryption key"})}

    except Exception as e:
        logger.error(f"Error in decrypt_data_key: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error"})}


@api_wrapper
def get_encryption_config(event: dict, context: dict) -> dict:
    """Get encryption configuration for the current user."""
    try:
        user_id = get_username(event)

        # Check if encryption is enabled via configuration table
        encryption_enabled = _is_session_encryption_enabled()
        kms_key_arn = os.environ.get("SESSION_ENCRYPTION_KEY_ARN")

        return {
            "statusCode": 200,
            "body": json.dumps({"enabled": encryption_enabled, "kmsKeyArn": kms_key_arn, "userId": user_id}),
        }

    except Exception as e:
        logger.error(f"Error in get_encryption_config: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error"})}


@api_wrapper
def update_encryption_config(event: dict, context: dict) -> dict:
    """Update encryption configuration (admin only)."""
    try:
        user_id = get_username(event)  # Will be used for admin role check  # noqa: F841

        # Parse request body
        try:
            body = json.loads(event.get("body", "{}"))  # noqa: P103
        except json.JSONDecodeError as e:
            return {"statusCode": 400, "body": json.dumps({"error": f"Invalid JSON: {e}"})}

        # TODO: Add admin role check here
        # For now, we'll just return success
        # In a real implementation, you'd want to:
        # 1. Check if user has admin privileges
        # 2. Update the configuration in a database or parameter store
        # 3. Potentially trigger session migration

        enabled = body.get("enabled", True)

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Encryption configuration updated successfully", "enabled": enabled}),
        }

    except Exception as e:
        logger.error(f"Error in update_encryption_config: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error"})}
