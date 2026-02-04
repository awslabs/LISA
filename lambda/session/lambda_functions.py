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
from decimal import Decimal
from typing import Any

import boto3
import create_env_variables  # noqa: F401
from botocore.exceptions import ClientError
from cachetools import cached, TTLCache  # type: ignore[import-untyped,unused-ignore]
from metrics.models import MetricsEvent
from models.domain_objects import DeleteResponse, SuccessResponse
from pydantic import ValidationError
from session.models import (
    AttachImageRequest,
    PutSessionRequest,
    RenameSessionRequest,
    Session,
    SessionSummary,
)
from utilities.auth import get_user_context, get_username
from utilities.common_functions import api_wrapper, get_session_id, retry_config
from utilities.encoders import convert_decimal
from utilities.input_validation import MAX_LARGE_REQUEST_SIZE
from utilities.session_encryption import decrypt_session_fields, migrate_session_to_encrypted, SessionEncryptionError
from utilities.time import iso_string

logger = logging.getLogger(__name__)

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
s3_client = boto3.client("s3", region_name=os.environ["AWS_REGION"], config=retry_config)
s3_resource = boto3.resource("s3", region_name=os.environ["AWS_REGION"])
sqs_client = boto3.client("sqs", region_name=os.environ["AWS_REGION"], config=retry_config)
table = dynamodb.Table(os.environ["SESSIONS_TABLE_NAME"])
s3_bucket_name = os.environ["GENERATED_IMAGES_S3_BUCKET_NAME"]

# Get model table for real-time feature validation
model_table = dynamodb.Table(os.environ.get("MODEL_TABLE_NAME"))

# Get configuration table for system settings
config_table = dynamodb.Table(os.environ["CONFIG_TABLE_NAME"])

executor = ThreadPoolExecutor(max_workers=10)

# Cache for configuration values to avoid repeated database queries
cache: TTLCache = TTLCache(maxsize=1, ttl=300)  # 5 minutes


@cached(cache=cache)
def _is_session_encryption_enabled() -> bool:
    """Check if session encryption is enabled via global configuration.

    Returns
    -------
    bool
        True if session encryption is enabled, False otherwise.
        Defaults to False if configuration is not found or accessible.
    """

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
            logger.info(f"Retrieved session encryption setting from global config: {encrypt_session}")
            return encrypt_session  # type: ignore[no-any-return]
        else:
            logger.warning("No global configuration found, defaulting session encryption to disabled")
            return False

    except ClientError as error:
        logger.error(f"Failed to query global configuration: {error}, defaulting to encryption disabled")
        return False
    except Exception as e:
        logger.error(f"Error checking session encryption configuration: {e}, defaulting to disabled")
        return False


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


def _update_session_with_current_model_config(session_config: dict[str, Any]) -> dict[str, Any]:
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


def _get_all_user_sessions(user_id: str) -> list[dict[str, Any]]:
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


def _extract_video_s3_keys(session: dict) -> list[str]:
    """Extract all video S3 keys from a session's history.

    Parameters
    ----------
    session : dict
        The session object containing history.

    Returns
    -------
    list[str]
        A list of S3 keys for videos in the session.
    """
    video_keys: list[str] = []
    for message in session.get("history", []):
        content = message.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "video_url":
                    video_url = item.get("video_url", {})
                    s3_key = video_url.get("s3_key")
                    if s3_key:
                        video_keys.append(s3_key)
    return video_keys


def _delete_user_session(session_id: str, user_id: str) -> DeleteResponse:
    """Delete a session from DynamoDB.

    Parameters
    ----------
    session_id : str
        The session id.
    user_id : str
        The user id.

    Returns
    -------
    DeleteResponse
        Response containing the deleted status.
    """
    deleted = False
    try:
        # First, get the session to extract any video S3 keys before deleting
        response = table.get_item(Key={"sessionId": session_id, "userId": user_id})
        session = response.get("Item", {})

        # Decrypt session if encrypted to access history for video keys
        if session.get("is_encrypted", False):
            try:
                logger.info(f"Decrypting session {session_id} to extract video keys for deletion")
                session = decrypt_session_fields(session, user_id, session_id)
            except SessionEncryptionError as e:
                logger.warning(f"Failed to decrypt session {session_id} for video cleanup: {e}")
                # Continue with deletion even if decryption fails - videos may remain orphaned

        # Extract video S3 keys from the session history
        video_keys = _extract_video_s3_keys(session)

        # Delete the session from DynamoDB
        table.delete_item(Key={"sessionId": session_id, "userId": user_id})

        # Delete associated images from S3
        bucket = s3_resource.Bucket(s3_bucket_name)
        bucket.objects.filter(Prefix=f"images/{session_id}").delete()

        # Delete associated videos from S3
        if video_keys:
            logger.info(f"Deleting {len(video_keys)} videos from S3 for session {session_id}")
            for video_key in video_keys:
                try:
                    s3_client.delete_object(Bucket=s3_bucket_name, Key=video_key)
                    logger.debug(f"Deleted video: {video_key}")
                except ClientError as video_error:
                    logger.warning(f"Failed to delete video {video_key}: {video_error}")

        deleted = True
    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.warning(f"No record found with session id: {session_id}")
        else:
            logger.exception("Error deleting session")
    return DeleteResponse(deleted=deleted)


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


def _generate_presigned_video_url(key: str) -> str:
    url: str = s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": s3_bucket_name,
            "Key": key,
            "ResponseContentType": "video/mp4",
            "ResponseCacheControl": "no-cache",
            "ResponseContentDisposition": "inline",
        },
    )
    return url


def _map_session(session: dict, user_id: str | None = None) -> SessionSummary:
    return SessionSummary(
        sessionId=session.get("sessionId"),
        name=session.get("name"),
        firstHumanMessage=_find_first_human_message(session, user_id),
        startTime=session.get("startTime"),
        createTime=session.get("createTime"),
        lastUpdated=session.get("lastUpdated", session.get("startTime")),
        isEncrypted=session.get("is_encrypted", False),
    )


def _find_first_human_message(session: dict, user_id: str | None = None) -> str:
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
def list_sessions(event: dict, context: dict) -> list[SessionSummary]:
    """List sessions by user ID from DynamoDB."""
    user_id = get_username(event)

    logger.info(f"Listing sessions for user {user_id}")
    sessions = _get_all_user_sessions(user_id)

    return list(executor.map(lambda session: _map_session(session, user_id), sessions))


def _process_image(task: tuple[dict, str]) -> None:
    msg, key = task
    try:
        image_url = _generate_presigned_image_url(key)
        msg["image_url"]["url"] = image_url
    except Exception as e:
        print(f"Error generating presigned image URL: {e}")


def _process_video(task: tuple[dict, str]) -> None:
    msg, key = task
    try:
        video_url = _generate_presigned_video_url(key)
        msg["video_url"]["url"] = video_url
    except Exception as e:
        print(f"Error generating presigned video URL: {e}")


@api_wrapper
def get_session(event: dict, context: dict) -> Session | dict:
    """Get a session from DynamoDB."""
    try:
        user_id = get_username(event)
        session_id = get_session_id(event)

        logging.info(f"Fetching session with ID {session_id} for user {user_id}")

        response = table.get_item(Key={"sessionId": session_id, "userId": user_id})
        item = response.get("Item", {})

        if not item:
            return {"statusCode": 404, "body": json.dumps({"error": "Session not found"})}

        # Check if session data is encrypted and decrypt if necessary
        try:
            if item.get("is_encrypted", False):
                logging.info(f"Decrypting encrypted session {session_id} for user {user_id}")
                item = decrypt_session_fields(item, user_id, session_id)
        except SessionEncryptionError as e:
            logging.error(f"Failed to decrypt session {session_id}: {e}")
            return {"statusCode": 500, "body": json.dumps({"error": "Failed to decrypt session data"})}

        # Create Session object from DynamoDB item
        session = Session.from_dynamodb_item(item)

        # Update configuration with current model settings before returning
        if session.configuration and session.configuration.get("selectedModel"):
            temp_config = {"selectedModel": session.configuration["selectedModel"]}
            updated_temp_config = _update_session_with_current_model_config(temp_config)
            session.configuration["selectedModel"] = updated_temp_config.get(
                "selectedModel", session.configuration["selectedModel"]
            )

        # Create a list of tasks for parallel processing presigned URLs
        image_tasks = []
        video_tasks = []
        for message in session.history:
            if isinstance(message.get("content"), list):
                for item in message.get("content", []):
                    if item.get("type") == "image_url":
                        s3_key = item.get("image_url", {}).get("s3_key")
                        if s3_key:
                            image_tasks.append((item, s3_key))
                    elif item.get("type") == "video_url":
                        s3_key = item.get("video_url", {}).get("s3_key")
                        if s3_key:
                            video_tasks.append((item, s3_key))

        list(executor.map(_process_image, image_tasks))
        list(executor.map(_process_video, video_tasks))
        return session
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}


@api_wrapper
def delete_session(event: dict, context: dict) -> DeleteResponse:
    """Delete session from DynamoDB."""
    user_id = get_username(event)
    session_id = get_session_id(event)

    logger.info(f"Deleting session with ID {session_id} for user {user_id}")
    return _delete_user_session(session_id, user_id)


@api_wrapper
def delete_user_sessions(event: dict, context: dict) -> DeleteResponse:
    """Delete sessions by user ID from DyanmoDB."""
    user_id = get_username(event)

    logger.info(f"Deleting all sessions for user {user_id}")
    sessions = _get_all_user_sessions(user_id)
    logger.debug(f"Found user sessions: {sessions}")

    list(executor.map(lambda session: _delete_user_session(session["sessionId"], user_id), sessions))
    return DeleteResponse(deleted=True)


@api_wrapper(max_request_size=MAX_LARGE_REQUEST_SIZE)
def attach_image_to_session(event: dict, context: dict) -> dict:
    """Append the message to the record in DynamoDB."""
    try:
        session_id = get_session_id(event)

        try:
            body = json.loads(event["body"], parse_float=Decimal)
        except json.JSONDecodeError as e:
            return {"statusCode": 400, "body": json.dumps({"error": f"Invalid JSON: {str(e)}"})}

        try:
            request = AttachImageRequest.model_validate(body)
        except ValidationError as e:
            return {"statusCode": 400, "body": json.dumps({"error": str(e)})}

        message = request.message
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
def rename_session(event: dict, context: dict) -> SuccessResponse | dict:
    """Update session name in DynamoDB."""
    try:
        user_id = get_username(event)
        session_id = get_session_id(event)

        try:
            body = json.loads(event.get("body", {}), parse_float=Decimal)
        except json.JSONDecodeError as e:
            return {"statusCode": 400, "body": json.dumps({"error": f"Invalid JSON: {str(e)}"})}

        try:
            request = RenameSessionRequest.model_validate(body)
        except ValidationError as e:
            return {"statusCode": 400, "body": json.dumps({"error": str(e)})}

        table.update_item(
            Key={"sessionId": session_id, "userId": user_id},
            UpdateExpression="SET #name = :name, #lastUpdated = :lastUpdated",
            ExpressionAttributeNames={"#name": "name", "#lastUpdated": "lastUpdated"},
            ExpressionAttributeValues={":name": request.name, ":lastUpdated": iso_string()},
        )
        return SuccessResponse(message="Session name updated successfully")
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}


@api_wrapper(max_request_size=MAX_LARGE_REQUEST_SIZE)
def put_session(event: dict, context: dict) -> SuccessResponse | dict:
    """Append the message to the record in DynamoDB."""
    try:
        user_id, _, groups = get_user_context(event)
        session_id = get_session_id(event)

        try:
            body = json.loads(event["body"], parse_float=Decimal)
        except json.JSONDecodeError as e:
            return {"statusCode": 400, "body": json.dumps({"error": f"Invalid JSON: {str(e)}"})}

        try:
            request = PutSessionRequest.model_validate(body)
        except ValidationError as e:
            return {"statusCode": 400, "body": json.dumps({"error": str(e)})}

        # Get the configuration from the request body (what the frontend sends)
        configuration = request.configuration or {}

        # Update the selectedModel within the configuration with current model settings
        if configuration and configuration.get("selectedModel"):
            temp_config = {"selectedModel": configuration["selectedModel"]}
            updated_temp_config = _update_session_with_current_model_config(temp_config)
            configuration["selectedModel"] = updated_temp_config.get("selectedModel", configuration["selectedModel"])

        # Check if encryption is enabled via configuration table
        encryption_enabled = _is_session_encryption_enabled()

        # Prepare session data for storage
        session_data = request.to_session_data(configuration)

        # Encrypt sensitive data if encryption is enabled
        if encryption_enabled:
            try:
                logging.info(f"Encrypting session {session_id} for user {user_id}")
                encrypted_session = migrate_session_to_encrypted(session_data.model_dump(), user_id, session_id)

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
                + "#lastUpdated = :lastUpdated, #is_encrypted = :is_encrypted",
                ExpressionAttributeNames={
                    "#history": "history",
                    "#name": "name",
                    "#configuration": "configuration",
                    "#startTime": "startTime",
                    "#createTime": "createTime",
                    "#lastUpdated": "lastUpdated",
                    "#is_encrypted": "is_encrypted",
                },
                ExpressionAttributeValues={
                    ":history": session_data.history,
                    ":name": session_data.name,
                    ":configuration": session_data.configuration,
                    ":startTime": session_data.startTime,
                    ":createTime": session_data.createTime,
                    ":lastUpdated": session_data.lastUpdated,
                    ":is_encrypted": False,
                },
                ReturnValues="UPDATED_NEW",
            )

        # Publish metrics to SQS queue for non-API-token users
        # API token users have their metrics tracked in litellm_passthrough.py
        try:
            # Get auth type from authorizer context
            request_context = event.get("requestContext", {})
            authorizer_context = request_context.get("authorizer", {})
            auth_type = authorizer_context.get("authType", "jwt")  # Default to jwt for backwards compatibility

            # Only publish metrics for non-API-token users (JWT/UI users)
            if auth_type != "api_token" and "USAGE_METRICS_QUEUE_NAME" in os.environ:
                metrics_event = MetricsEvent(
                    userId=user_id,
                    sessionId=session_id,
                    messages=session_data.history,
                    userGroups=groups,
                    timestamp=session_data.lastUpdated,
                )
                sqs_client.send_message(
                    QueueUrl=os.environ["USAGE_METRICS_QUEUE_NAME"],
                    MessageBody=json.dumps(convert_decimal(metrics_event.model_dump())),
                )
                logger.info(f"Published metrics event to queue for user: {user_id}")
            else:
                logger.warning("USAGE_METRICS_QUEUE_NAME environment variable not set, metrics not published")
        except Exception as e:
            logger.error(f"Failed to publish to metrics queue: {e}")

        return SuccessResponse(message="Session updated successfully")
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}
