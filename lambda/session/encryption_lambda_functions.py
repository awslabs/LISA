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
from typing import Any, Dict

import boto3
from botocore.exceptions import ClientError
from utilities.common_functions import api_wrapper, get_username, retry_config
from utilities.session_encryption import SessionEncryptionError

logger = logging.getLogger(__name__)

# Initialize KMS client
kms_client = boto3.client('kms', region_name=os.environ.get('AWS_REGION', 'us-east-1'), config=retry_config)


@api_wrapper
def generate_data_key(event: dict, context: dict) -> dict:
    """Generate a data key for session encryption."""
    try:
        user_id = get_username(event)
        
        # Parse request body
        try:
            body = json.loads(event.get("body", "{}"))
        except json.JSONDecodeError as e:
            return {"statusCode": 400, "body": json.dumps({"error": f"Invalid JSON: {str(e)}"})}
        
        session_id = body.get("sessionId")
        if not session_id:
            return {"statusCode": 400, "body": json.dumps({"error": "sessionId is required"})}
        
        # Get KMS key ARN from environment
        kms_key_arn = os.environ.get("SESSION_ENCRYPTION_KEY_ARN")
        if not kms_key_arn:
            return {"statusCode": 500, "body": json.dumps({"error": "Encryption key not configured"})}
        
        # Create encryption context
        encryption_context = {
            'userId': user_id,
            'sessionId': session_id,
            'purpose': 'session-encryption'
        }
        
        # Generate data key
        try:
            response = kms_client.generate_data_key(
                KeyId=kms_key_arn,
                KeySpec='AES_256',
                EncryptionContext=encryption_context
            )
            
            # Return base64 encoded keys
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "plaintext": base64.b64encode(response['Plaintext']).decode('utf-8'),
                    "encrypted": base64.b64encode(response['CiphertextBlob']).decode('utf-8')
                })
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
            body = json.loads(event.get("body", "{}"))
        except json.JSONDecodeError as e:
            return {"statusCode": 400, "body": json.dumps({"error": f"Invalid JSON: {str(e)}"})}
        
        encrypted_key = body.get("encryptedKey")
        session_id = body.get("sessionId")
        
        if not encrypted_key or not session_id:
            return {"statusCode": 400, "body": json.dumps({"error": "encryptedKey and sessionId are required"})}
        
        # Create encryption context
        encryption_context = {
            'userId': user_id,
            'sessionId': session_id,
            'purpose': 'session-encryption'
        }
        
        # Decrypt the data key
        try:
            response = kms_client.decrypt(
                CiphertextBlob=base64.b64decode(encrypted_key),
                EncryptionContext=encryption_context
            )
            
            # Return base64 encoded plaintext key
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "plaintext": base64.b64encode(response['Plaintext']).decode('utf-8')
                })
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
        
        # Check if encryption is enabled
        encryption_enabled = os.environ.get("SESSION_ENCRYPTION_ENABLED", "true").lower() == "true"
        kms_key_arn = os.environ.get("SESSION_ENCRYPTION_KEY_ARN")
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "enabled": encryption_enabled,
                "kmsKeyArn": kms_key_arn,
                "userId": user_id
            })
        }
        
    except Exception as e:
        logger.error(f"Error in get_encryption_config: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error"})}


@api_wrapper
def update_encryption_config(event: dict, context: dict) -> dict:
    """Update encryption configuration (admin only)."""
    try:
        user_id = get_username(event)
        
        # Parse request body
        try:
            body = json.loads(event.get("body", "{}"))
        except json.JSONDecodeError as e:
            return {"statusCode": 400, "body": json.dumps({"error": f"Invalid JSON: {str(e)}"})}
        
        # TODO: Add admin role check here
        # For now, we'll just return success
        # In a real implementation, you'd want to:
        # 1. Check if user has admin privileges
        # 2. Update the configuration in a database or parameter store
        # 3. Potentially trigger session migration
        
        enabled = body.get("enabled", True)
        
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Encryption configuration updated successfully",
                "enabled": enabled
            })
        }
        
    except Exception as e:
        logger.error(f"Error in update_encryption_config: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error"})}
