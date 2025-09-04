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

"""Lambda functions for managing sessions."""
import base64
import json
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import boto3
import create_env_variables  # noqa: F401
from botocore.exceptions import ClientError
from utilities.auth import get_username
from utilities.common_functions import api_wrapper, get_groups, get_session_id, retry_config
from utilities.encoders import convert_decimal
from utilities.session_encryption import decrypt_session_fields, migrate_session_to_encrypted, SessionEncryptionError

logger = logging.getLogger(__name__)

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
s3_client = boto3.client("s3", region_name=os.environ["AWS_REGION"], config=retry_config)
s3_resource = boto3.resource("s3", region_name=os.environ["AWS_REGION"])
sqs_client = boto3.client("sqs", region_name=os.environ["AWS_REGION"], config=retry_config)
table = dynamodb.Table(os.environ["SESSIONS_TABLE_NAME"])
s3_bucket_name = os.environ["GENERATED_IMAGES_S3_BUCKET_NAME"]

# Get model table for real-time feature validation
model_table = dynamodb.Table(os.environ.get("MODEL_TABLE_NAME"))

executor = ThreadPoolExecutor(max_workers=10)


def _get_current_model_config(model_id: str) -> Any:
    """Get the current model configuration from the model table.

    Parameters
    ----------
    model_id : str
        The model ID to fetch configuration for.

    Returns
    -------
    Dict[str, Any]
        The current model configuration, or empty dict if not found.
    """
    if not model_table or not model_id:
        return {}

    try:
        response = model_table.get_item(Key={"model_id": model_id})
        model_item = response.get("Item", {})
        return model_item.get("model_config", {})
    except ClientError as error:
        logger.warning(f"Could not fetch model config for {model_id}: {error}")
        return {}


def _update_session_with_current_model_config(session_config: Dict[str, Any]) -> Dict[str, Any]:
    """Update session configuration with the most recent model configuration.

    Parameters
    ----------
    session_config : Dict[str, Any]
        The session configuration containing model information.

    Returns
    -------
    Dict[str, Any]
        Updated configuration with current model settings.
    """
    if not session_config:
        return session_config

    # Extract model ID from selectedModel section
    selected_model = session_config.get("selectedModel", {})

    # Get the modelId directly
    model_id = selected_model.get("modelId")
    if not model_id:
        logger.warning("No modelId found in session selectedModel")
        return session_config

    current_model_config = _get_current_model_config(model_id)

    if not current_model_config:
        logger.warning(f"Could not fetch current config for model {model_id}, using existing session config")
        return session_config

    # Create updated config with current model settings
    updated_config = session_config.copy()

    # Update the selectedModel section with current model configuration
    if "selectedModel" not in updated_config:
        updated_config["selectedModel"] = {}

    selected_model_section = updated_config["selectedModel"]

    # Update features from current model config
    if "features" in current_model_config:
        selected_model_section["features"] = current_model_config["features"]

    # Update streaming setting
    if "streaming" in current_model_config:
        selected_model_section["streaming"] = current_model_config["streaming"]

    # Update other model-specific settings that might have changed
    for key in ["modelType", "modelDescription", "allowedGroups"]:
        if key in current_model_config:
            selected_model_section[key] = current_model_config[key]

    logger.info(f"Updated session selectedModel config for model {model_id} with current model settings")
    return updated_config


def _get_all_user_sessions(user_id: str) -> List[Dict[str, Any]]:
    """Get all sessions for a user from DynamoDB.

    Parameters
    ----------
    user_id : str
        The user id.

    Returns
    -------
    List[Dict[str, Any]]
        A list of user sessions.
    """
    response = {}
    try:
        response = table.query(
            KeyConditionExpression="userId = :user_id",
            ExpressionAttributeValues={":user_id": user_id},
            IndexName=os.environ["SESSIONS_BY_USER_ID_INDEX_NAME"],
            ScanIndexForward=False,
        )
    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.warning(f"No sessions found for user {user_id}")
        else:
            logger.exception("Error listing sessions")
    return response.get("Items", [])  # type: ignore [no-any-return]


def _delete_user_session(session_id: str, user_id: str) -> Dict[str, bool]:
    """Delete a session from DynamoDB.

    Parameters
    ----------
    session_id : str
        The session id.
    user_id : str
        The user id.

    Returns
    -------
    Dict[str, bool]
        A dictionary containing the deleted status.
    """
    deleted = False
    try:
        table.delete_item(Key={"sessionId": session_id, "userId": user_id})
        bucket = s3_resource.Bucket(s3_bucket_name)
        bucket.objects.filter(Prefix=f"images/{session_id}").delete()
        deleted = True
    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.warning(f"No record found with session id: {session_id}")
        else:
            logger.exception("Error deleting session")
    return {"deleted": deleted}


def _generate_presigned_image_url(key: str) -> str:
    url: str = s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": s3_bucket_name,
            "Key": key,
            "ResponseContentType": "image/png",
            "ResponseCacheControl": "no-cache",
            "ResponseContentDisposition": "inline",
        },
    )
    return url


def _map_session(session: dict, user_id: Optional[str] = None) -> Dict[str, Any]:
    return {
        "sessionId": session.get("sessionId", None),
        "name": session.get("name", None),
        "firstHumanMessage": _find_first_human_message(session, user_id),
        "startTime": session.get("startTime", None),
        "createTime": session.get("createTime", None),
        "lastUpdated": session.get(
            "lastUpdated", session.get("startTime", None)
        ),  # Fallback to startTime for backward compatibility
        "isEncrypted": session.get("is_encrypted", False),
    }


def _find_first_human_message(session: dict, user_id: Optional[str] = None) -> str:
    # Check if session is encrypted
    if session.get("is_encrypted", False):
        # For encrypted sessions, decrypt to get the first message
        try:
            if user_id:
                logging.info(
                    f"Decrypting encrypted session {session.get('sessionId', 'unknown')} "
                    f"to find first message for user {user_id}"
                )
                decrypted_session = decrypt_session_fields(session, user_id, session.get("sessionId", ""))
                # Use the decrypted session for finding the first message
                session = decrypted_session
            else:
                # If no user_id provided, return placeholder
                return "[Encrypted Session - User ID required]"
        except SessionEncryptionError as e:
            logging.error(f"Failed to decrypt session {session.get('sessionId', 'unknown')} to find first message: {e}")
            return "[Encrypted Session - Decryption failed]"

    # For unencrypted sessions (or successfully decrypted sessions), proceed as before
    for msg in session.get("history", []):
        if msg.get("type") == "human":
            content = msg.get("content")
            if isinstance(content, str):
                return content
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        text: str = item.get("text", "")
                        if text and not text.startswith("File context:"):
                            return text
            else:
                logger.warning(f"Unhandled human message content in session {session.get('sessionId', 'unknown')}")
    return ""


@api_wrapper
def list_sessions(event: dict, context: dict) -> List[Dict[str, Any]]:
    """List sessions by user ID from DynamoDB."""
    user_id = get_username(event)

    logger.info(f"Listing sessions for user {user_id}")
    sessions = _get_all_user_sessions(user_id)

    return list(executor.map(lambda session: _map_session(session, user_id), sessions))


def _process_image(task: Tuple[dict, str]) -> None:
    msg, key = task
    try:
        image_url = _generate_presigned_image_url(key)
        msg["image_url"]["url"] = image_url
    except Exception as e:
        print(f"Error uploading to S3: {e}")


@api_wrapper
def get_session(event: dict, context: dict) -> dict:
    """Get a session from DynamoDB."""
    try:
        user_id = get_username(event)
        session_id = get_session_id(event)

        logging.info(f"Fetching session with ID {session_id} for user {user_id}")

        response = table.get_item(Key={"sessionId": session_id, "userId": user_id})
        resp = response.get("Item", {})

        if not resp:
            return {"statusCode": 404, "body": json.dumps({"error": "Session not found"})}

        # Check if session data is encrypted and decrypt if necessary
        try:
            if resp.get("is_encrypted", False):
                logging.info(f"Decrypting encrypted session {session_id} for user {user_id}")
                resp = decrypt_session_fields(resp, user_id, session_id)
        except SessionEncryptionError as e:
            logging.error(f"Failed to decrypt session {session_id}: {e}")
            return {"statusCode": 500, "body": json.dumps({"error": "Failed to decrypt session data"})}

        # Update configuration with current model settings before returning
        if resp and resp.get("configuration"):
            configuration = resp.get("configuration", {})
            # Update the selectedModel within the configuration with current model settings
            if configuration.get("selectedModel"):
                temp_config = {"selectedModel": configuration["selectedModel"]}
                updated_temp_config = _update_session_with_current_model_config(temp_config)
                configuration["selectedModel"] = updated_temp_config.get(
                    "selectedModel", configuration["selectedModel"]
                )
                # Update the configuration in the response
                resp["configuration"] = configuration

        # Create a list of tasks for parallel processing
        tasks = []
        for message in resp.get("history", []):
            if isinstance(message.get("content", None), List):
                for item in message.get("content", None):
                    if item.get("type", None) == "image_url":
                        s3_key = item.get("image_url", {}).get("s3_key", None)
                        if s3_key:
                            tasks.append((item, s3_key))

        list(executor.map(_process_image, tasks))
        return resp  # type: ignore [no-any-return]
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}


@api_wrapper
def delete_session(event: dict, context: dict) -> dict:
    """Delete session from DynamoDB."""
    user_id = get_username(event)
    session_id = get_session_id(event)

    logger.info(f"Deleting session with ID {session_id} for user {user_id}")
    return _delete_user_session(session_id, user_id)


@api_wrapper
def delete_user_sessions(event: dict, context: dict) -> Dict[str, bool]:
    """Delete sessions by user ID from DyanmoDB."""
    user_id = get_username(event)

    logger.info(f"Deleting all sessions for user {user_id}")
    sessions = _get_all_user_sessions(user_id)
    logger.debug(f"Found user sessions: {sessions}")

    list(executor.map(lambda session: _delete_user_session(session["sessionId"], user_id), sessions))
    return {"deleted": True}


@api_wrapper
def attach_image_to_session(event: dict, context: dict) -> dict:
    """Append the message to the record in DynamoDB."""
    try:
        session_id = get_session_id(event)

        try:
            body = json.loads(event["body"], parse_float=Decimal)
        except json.JSONDecodeError as e:
            return {"statusCode": 400, "body": json.dumps({"error": f"Invalid JSON: {str(e)}"})}

        if "message" not in body:
            return {"statusCode": 400, "body": json.dumps({"error": "Missing required fields: messages"})}

        message = body["message"]
        image_content = message.get("image_url", {}).get("url", None)

        if (
            message.get("type", None) == "image_url"
            and image_content is not None
            and not image_content.startswith("https://")
        ):
            try:
                # Generate a unique key for the S3 object
                file_name = f"{uuid.uuid4()}.png"
                s3_key = f"images/{session_id}/{file_name}"  # Organize files in an images/sessionId prefix

                # Upload to S3
                s3_client.put_object(
                    Bucket=s3_bucket_name,
                    Key=s3_key,
                    Body=base64.b64decode(image_content.split(",")[1]),
                    ContentType="image/png",
                )
                message["image_url"]["url"] = _generate_presigned_image_url(s3_key)
                message["image_url"]["s3_key"] = s3_key
            except Exception as e:
                print(f"Error uploading to S3: {e}")

        return {"statusCode": 200, "body": message}
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}


@api_wrapper
def rename_session(event: dict, context: dict) -> dict:
    """Update session name in DynamoDB."""
    try:
        user_id = get_username(event)
        session_id = get_session_id(event)

        try:
            body = json.loads(event.get("body", {}), parse_float=Decimal)
        except json.JSONDecodeError as e:
            return {"statusCode": 400, "body": json.dumps({"error": f"Invalid JSON: {str(e)}"})}

        if "name" not in body:
            return {"statusCode": 400, "body": json.dumps({"error": "Missing required field: name"})}

        table.update_item(
            Key={"sessionId": session_id, "userId": user_id},
            UpdateExpression="SET #name = :name, #lastUpdated = :lastUpdated",
            ExpressionAttributeNames={"#name": "name", "#lastUpdated": "lastUpdated"},
            ExpressionAttributeValues={":name": body.get("name"), ":lastUpdated": datetime.now().isoformat()},
        )
        return {"statusCode": 200, "body": json.dumps({"message": "Session name updated successfully"})}
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}


@api_wrapper
def put_session(event: dict, context: dict) -> dict:
    """Append the message to the record in DynamoDB."""
    try:
        user_id = get_username(event)
        session_id = get_session_id(event)

        try:
            body = json.loads(event["body"], parse_float=Decimal)
        except json.JSONDecodeError as e:
            return {"statusCode": 400, "body": json.dumps({"error": f"Invalid JSON: {str(e)}"})}

        if "messages" not in body:
            return {"statusCode": 400, "body": json.dumps({"error": "Missing required fields: messages"})}

        messages = body["messages"]

        # Get the configuration from the request body (what the frontend sends)
        configuration = body.get("configuration", {})

        # Update the selectedModel within the configuration with current model settings
        if configuration and configuration.get("selectedModel"):
            temp_config = {"selectedModel": configuration["selectedModel"]}
            updated_temp_config = _update_session_with_current_model_config(temp_config)
            configuration["selectedModel"] = updated_temp_config.get("selectedModel", configuration["selectedModel"])

        # Check if encryption is enabled (can be controlled via environment variable or configuration)
        encryption_enabled = os.environ.get("SESSION_ENCRYPTION_ENABLED", "true").lower() == "true"

        # Prepare session data for storage
        session_data = {
            "history": messages,
            "name": body.get("name", None),
            "configuration": configuration,
            "startTime": datetime.now().isoformat(),
            "createTime": datetime.now().isoformat(),
            "lastUpdated": datetime.now().isoformat(),
        }

        # Encrypt sensitive data if encryption is enabled
        if encryption_enabled:
            try:
                logging.info(f"Encrypting session {session_id} for user {user_id}")
                encrypted_session = migrate_session_to_encrypted(session_data, user_id, session_id)

                # Update DynamoDB with encrypted data
                table.update_item(
                    Key={"sessionId": session_id, "userId": user_id},
                    UpdateExpression="SET #encrypted_history = :encrypted_history, #name = :name, "
                    + "#encrypted_configuration = :encrypted_configuration, #startTime = :startTime, "
                    + "#createTime = if_not_exists(#createTime, :createTime), #lastUpdated = :lastUpdated, "
                    + "#encryption_version = :encryption_version, #is_encrypted = :is_encrypted",
                    ExpressionAttributeNames={
                        "#encrypted_history": "encrypted_history",
                        "#name": "name",
                        "#encrypted_configuration": "encrypted_configuration",
                        "#startTime": "startTime",
                        "#createTime": "createTime",
                        "#lastUpdated": "lastUpdated",
                        "#encryption_version": "encryption_version",
                        "#is_encrypted": "is_encrypted",
                    },
                    ExpressionAttributeValues={
                        ":encrypted_history": encrypted_session["encrypted_history"],
                        ":name": encrypted_session["name"],
                        ":encrypted_configuration": encrypted_session["encrypted_configuration"],
                        ":startTime": encrypted_session["startTime"],
                        ":createTime": encrypted_session["createTime"],
                        ":lastUpdated": encrypted_session["lastUpdated"],
                        ":encryption_version": encrypted_session["encryption_version"],
                        ":is_encrypted": encrypted_session["is_encrypted"],
                    },
                    ReturnValues="UPDATED_NEW",
                )
            except SessionEncryptionError as e:
                logging.error(f"Failed to encrypt session {session_id}: {e}")
                return {"statusCode": 500, "body": json.dumps({"error": "Failed to encrypt session data"})}
        else:
            # Store unencrypted data (legacy mode)
            table.update_item(
                Key={"sessionId": session_id, "userId": user_id},
                UpdateExpression="SET #history = :history, #name = :name, #configuration = :configuration, "
                + "#startTime = :startTime, #createTime = if_not_exists(#createTime, :createTime), "
                + "#lastUpdated = :lastUpdated",
                ExpressionAttributeNames={
                    "#history": "history",
                    "#name": "name",
                    "#configuration": "configuration",
                    "#startTime": "startTime",
                    "#createTime": "createTime",
                    "#lastUpdated": "lastUpdated",
                },
                ExpressionAttributeValues={
                    ":history": messages,
                    ":name": body.get("name", None),
                    ":configuration": configuration,
                    ":startTime": datetime.now().isoformat(),
                    ":createTime": datetime.now().isoformat(),
                    ":lastUpdated": datetime.now().isoformat(),
                },
                ReturnValues="UPDATED_NEW",
            )

        # Publish event to SQS queue for metrics processing (use unencrypted data for metrics)
        try:
            if "USAGE_METRICS_QUEUE_NAME" in os.environ:
                # Create a copy of the event to send to SQS
                metrics_event = {
                    "userId": user_id,
                    "sessionId": session_id,
                    "messages": messages,
                    "userGroups": get_groups(event),
                    "timestamp": datetime.now().isoformat(),
                }
                sqs_client.send_message(
                    QueueUrl=os.environ["USAGE_METRICS_QUEUE_NAME"],
                    MessageBody=json.dumps(convert_decimal(metrics_event)),
                )
                logger.info(f"Published event to metrics queue for user {user_id}")
            else:
                logger.warning("USAGE_METRICS_QUEUE_NAME environment variable not set, metrics not published")
        except Exception as e:
            logger.error(f"Failed to publish to metrics queue: {e}")

        return {"statusCode": 200, "body": json.dumps({"message": "Session updated successfully"})}
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}
