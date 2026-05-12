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
import time
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
    PaginatedMessagesResponse,
    PostMessagesRequest,
    PutSessionRequest,
    RenameSessionRequest,
    SelectedModelFeature,
    Session,
    SessionConfigurationModel,
    SessionSummary,
)
from session.repository import delete_user_session, extract_video_s3_keys, get_all_user_sessions
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
messages_table = dynamodb.Table(os.environ["MESSAGES_TABLE_NAME"]) if os.environ.get("MESSAGES_TABLE_NAME") else None
projects_table = dynamodb.Table(os.environ["PROJECTS_TABLE_NAME"]) if os.environ.get("PROJECTS_TABLE_NAME") else None
s3_bucket_name = os.environ.get("GENERATED_IMAGES_S3_BUCKET_NAME", "")

# Get model table for real-time feature validation
model_table = dynamodb.Table(os.environ["MODEL_TABLE_NAME"]) if os.environ.get("MODEL_TABLE_NAME") else None

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


def _update_session_with_current_model_config(
    session_config: SessionConfigurationModel,
) -> SessionConfigurationModel:
    """Update session configuration with the most recent model configuration.

    Parameters
    ----------
    session_config : SessionConfigurationModel
        The session configuration containing model information.

    Returns
    -------
    SessionConfigurationModel
        Updated configuration with current model settings.
    """
    if not session_config or not session_config.selectedModel:
        return session_config

    selected_model = session_config.selectedModel
    model_id = selected_model.modelId
    if not model_id:
        logger.warning("No modelId found in session selectedModel")
        return session_config

    current_model_config = _get_current_model_config(model_id)

    if not current_model_config:
        logger.warning(f"Could not fetch current config for model {model_id}, using existing session config")
        return session_config

    # Build updated SelectedModel with current model settings
    updated_selected = selected_model.model_copy(deep=True)

    if "features" in current_model_config:
        updated_selected.features = [
            SelectedModelFeature.model_validate(f) if isinstance(f, dict) else f
            for f in current_model_config["features"]
        ]
    if "streaming" in current_model_config:
        updated_selected.streaming = current_model_config["streaming"]
    if "modelType" in current_model_config:
        updated_selected.modelType = str(current_model_config["modelType"])
    if "modelDescription" in current_model_config:
        updated_selected.modelDescription = current_model_config["modelDescription"]
    if "allowedGroups" in current_model_config:
        updated_selected.allowedGroups = current_model_config["allowedGroups"]

    logger.info(f"Updated session selectedModel config for model {model_id} with current model settings")
    updated_config: SessionConfigurationModel = session_config.model_copy(update={"selectedModel": updated_selected})
    return updated_config


def _get_all_user_sessions(user_id: str) -> list[dict[str, Any]]:
    return get_all_user_sessions(table, user_id)


def _delete_user_session(session_id: str, user_id: str) -> DeleteResponse:
    return delete_user_session(
        table, s3_resource, s3_client, s3_bucket_name, session_id, user_id,
        messages_table=messages_table, dynamodb_resource=dynamodb,
    )


def _extract_video_s3_keys(session: dict) -> list[str]:
    return extract_video_s3_keys(session)


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


def _map_session(
    session: dict, user_id: str | None = None, valid_project_ids: set[str] | None = None
) -> SessionSummary:
    raw_project_id = session.get("projectId")
    # Resolve dangling projectId: treat as None if not in the validated set
    resolved_project_id = (
        raw_project_id
        if (raw_project_id and valid_project_ids is not None and raw_project_id in valid_project_ids)
        else None
    )
    raw_tokens = session.get("totalTokensUsed")
    total_tokens_used = int(raw_tokens) if raw_tokens is not None else None
    return SessionSummary(
        sessionId=session.get("sessionId"),
        name=session.get("name"),
        firstHumanMessage=_find_first_human_message(session, user_id),
        startTime=session.get("startTime"),
        createTime=session.get("createTime"),
        lastUpdated=session.get("lastUpdated", session.get("startTime")),
        isEncrypted=session.get("is_encrypted", False),
        projectId=resolved_project_id,
        totalTokensUsed=total_tokens_used,
    )


def _strip_context_from_display_text(text: str) -> str:
    cleaned = text.strip()
    context_prefixes = ("File context:", "Context from document search:")

    if any(cleaned.startswith(prefix) for prefix in context_prefixes):
        return ""

    return cleaned


def _find_first_human_message(session: dict, user_id: str | None = None) -> str:
    session_id = session.get("sessionId", "")
    storage_version = session.get("storageVersion", "1.0")

    # For v2.0 sessions, messages are in the separate messages table — query for first human message
    if storage_version == "2.0" and messages_table and user_id:
        try:
            # Query messages in ascending order, looking for first human message
            msg_response = messages_table.query(
                KeyConditionExpression="sessionId = :sid",
                ExpressionAttributeValues={":sid": session_id},
                ScanIndexForward=True,
                Limit=10,  # Usually the first human is within the first few messages
            )
            for msg_item in msg_response.get("Items", []):
                if msg_item.get("type") == "human":
                    content = msg_item.get("content")
                    # Decrypt content if encrypted
                    if msg_item.get("is_encrypted") and content:
                        try:
                            from utilities.session_encryption import decrypt_session_data
                            decrypted = decrypt_session_data(content, user_id, session_id)
                            # Handle bundled payload {content, metadata, reasoningContent}
                            if isinstance(decrypted, dict) and "content" in decrypted:
                                content = decrypted["content"]
                            else:
                                content = decrypted
                        except Exception:
                            return "[Encrypted Message - Decryption failed]"
                    if isinstance(content, str):
                        cleaned = _strip_context_from_display_text(content)
                        if cleaned:
                            return cleaned
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict):
                                text = item.get("text", "")
                                if text:
                                    cleaned = _strip_context_from_display_text(text)
                                    if cleaned:
                                        return cleaned
        except Exception as e:
            logger.warning(f"Failed to query messages for first human message in session {session_id}: {e}")
        return ""

    # Legacy sessions: check if encrypted and decrypt
    if session.get("is_encrypted", False):
        try:
            if user_id:
                logging.info(
                    f"Decrypting encrypted session {session_id} "
                    f"to find first message for user {user_id}"
                )
                decrypted_session = decrypt_session_fields(session, user_id, session_id)
                session = decrypted_session
            else:
                return "[Encrypted Session - User ID required]"
        except SessionEncryptionError as e:
            logging.error(f"Failed to decrypt session {session_id} to find first message: {e}")
            return "[Encrypted Session - Decryption failed]"

    # For unencrypted sessions (or successfully decrypted sessions), proceed as before
    for msg in session.get("history", []):
        if msg.get("type") == "human":
            content = msg.get("content")
            if isinstance(content, str):
                cleaned = _strip_context_from_display_text(content)
                if cleaned:
                    return cleaned
            elif isinstance(content, list):
                for item in content:
                    if isinstance(item, dict):
                        text: str = item.get("text", "")
                        if text:
                            cleaned = _strip_context_from_display_text(text)
                            if cleaned:
                                return cleaned
            else:
                logger.warning(f"Unhandled human message content in session {session_id}")
    return ""


def _batch_get_valid_project_ids(dynamodb_client: Any, table_name: str, keys: list[dict]) -> set[str]:
    """Fetch valid project IDs via BatchGetItem, handling the 100-key limit and UnprocessedKeys."""
    valid: set[str] = set()
    pending_keys = list(keys)
    while pending_keys:
        chunk, pending_keys = pending_keys[:100], pending_keys[100:]
        request_items = {
            table_name: {
                "Keys": chunk,
                "ProjectionExpression": "projectId, #s",
                "ExpressionAttributeNames": {"#s": "status"},
            }
        }
        delay = 0.1
        for _attempt in range(5):
            resp = dynamodb_client.batch_get_item(RequestItems=request_items)
            for item in resp.get("Responses", {}).get(table_name, []):
                if item.get("status", {}).get("S") != "deleting":
                    valid.add(item["projectId"]["S"])
            unprocessed = resp.get("UnprocessedKeys", {})
            if not unprocessed:
                break
            request_items = unprocessed
            time.sleep(delay)
            delay = min(delay * 2, 5)
        else:
            logger.warning("BatchGetItem: gave up retrying UnprocessedKeys after 5 attempts")
    return valid


@api_wrapper
def list_sessions(event: dict, context: dict) -> list[SessionSummary]:
    """List sessions by user ID from DynamoDB."""
    user_id = get_username(event)

    logger.info(f"Listing sessions for user {user_id}")
    sessions = _get_all_user_sessions(user_id)

    valid_project_ids: set[str] = set()
    if projects_table is not None:
        unique_project_ids = {s["projectId"] for s in sessions if s.get("projectId")}
        if unique_project_ids:
            try:
                keys = [{"userId": {"S": user_id}, "projectId": {"S": pid}} for pid in unique_project_ids]
                dynamodb_client = boto3.client("dynamodb", region_name=os.environ["AWS_REGION"])
                valid_project_ids = _batch_get_valid_project_ids(dynamodb_client, projects_table.name, keys)
            except Exception as e:
                logger.warning(f"BatchGetItem for project validation failed: {e}")

    return list(executor.map(lambda session: _map_session(session, user_id, valid_project_ids), sessions))


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
    """Get a session from DynamoDB.

    Supports both storage versions:
    - Legacy (no storageVersion or "1.0"): reads history from the sessions table item
    - v2.0: reads messages from the separate messages table
    """
    try:
        user_id = get_username(event)
        session_id = get_session_id(event)

        logging.info(f"Fetching session with ID {session_id} for user {user_id}")

        response = table.get_item(Key={"sessionId": session_id, "userId": user_id})
        item = response.get("Item", {})

        if not item:
            return {"statusCode": 404, "body": json.dumps({"error": "Session not found"})}

        storage_version = item.get("storageVersion", "1.0")

        if storage_version == "2.0" and messages_table:
            # v2.0: Read messages from the separate messages table
            logger.info(f"Session {session_id} uses storageVersion 2.0, reading from messages table")

            # Decrypt configuration if encrypted
            config_data = item.get("configuration")
            if item.get("is_encrypted", False) and item.get("encrypted_configuration"):
                try:
                    from utilities.session_encryption import decrypt_session_data
                    config_data = decrypt_session_data(item["encrypted_configuration"], user_id, session_id)
                except Exception as e:
                    logger.warning(f"Failed to decrypt configuration for session {session_id}: {e}")
                    config_data = None

            # Build Session object from metadata (no history in the item)
            session = Session(
                sessionId=item.get("sessionId", ""),
                userId=item.get("userId", ""),
                history=[],
                name=item.get("name"),
                configuration=SessionConfigurationModel.from_dict(config_data),
                startTime=item.get("startTime"),
                createTime=item.get("createTime"),
                lastUpdated=item.get("lastUpdated"),
                projectId=item.get("projectId"),
            )

            # Query the most recent 20 messages (descending) then reverse for chronological order
            INITIAL_PAGE_SIZE = 20
            msg_query_params: dict[str, Any] = {
                "KeyConditionExpression": "sessionId = :sid",
                "ExpressionAttributeValues": {":sid": session_id},
                "ScanIndexForward": False,  # Descending (newest first)
                "Limit": INITIAL_PAGE_SIZE,
            }
            msg_response = messages_table.query(**msg_query_params)
            all_messages: list[dict[str, Any]] = msg_response.get("Items", [])
            last_evaluated_key = msg_response.get("LastEvaluatedKey")

            # Reverse to get chronological order (oldest first) for the frontend
            all_messages.reverse()

            # Set pagination cursor if there are more (older) messages
            has_more = last_evaluated_key is not None
            next_cursor = _encode_cursor(last_evaluated_key) if has_more else None

            # Decrypt message content if encrypted
            for msg_item in all_messages:
                if msg_item.get("is_encrypted") and msg_item.get("content"):
                    try:
                        from utilities.session_encryption import decrypt_session_data
                        decrypted = decrypt_session_data(msg_item["content"], user_id, session_id)
                        # The encrypted blob contains {content, metadata, reasoningContent}
                        if isinstance(decrypted, dict) and "content" in decrypted:
                            msg_item["content"] = decrypted["content"]
                            if decrypted.get("metadata"):
                                msg_item["metadata"] = decrypted["metadata"]
                            if decrypted.get("reasoningContent"):
                                msg_item["reasoningContent"] = decrypted["reasoningContent"]
                        else:
                            # Backward compat: older encrypted messages may have just content
                            msg_item["content"] = decrypted
                        del msg_item["is_encrypted"]
                    except Exception as e:
                        logger.warning(f"Failed to decrypt message {msg_item.get('messageIndex')}: {e}")

            session = session.model_copy(update={
                "history": all_messages,
                "nextCursor": next_cursor,
                "hasMoreMessages": has_more,
            })
        else:
            # Legacy (v1.0): Read history from the sessions table item
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
        if session.configuration and session.configuration.selectedModel:
            session = session.model_copy(
                update={"configuration": _update_session_with_current_model_config(session.configuration)}
            )

        # Create a list of tasks for parallel processing presigned URLs
        image_tasks = []
        video_tasks = []
        for message in session.history:
            if isinstance(message.get("content"), list):
                for content_item in message.get("content", []):
                    if content_item.get("type") == "image_url":
                        s3_key = content_item.get("image_url", {}).get("s3_key")
                        if s3_key:
                            image_tasks.append((content_item, s3_key))
                    elif content_item.get("type") == "video_url":
                        s3_key = content_item.get("video_url", {}).get("s3_key")
                        if s3_key:
                            video_tasks.append((content_item, s3_key))

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
        configuration = request.configuration or SessionConfigurationModel()

        # Update the selectedModel within the configuration with current model settings
        if configuration and configuration.selectedModel:
            configuration = _update_session_with_current_model_config(configuration)

        # Check if encryption is enabled via configuration table
        encryption_enabled = _is_session_encryption_enabled()

        # Prepare session data for storage
        session_data = request.to_session_data(configuration)

        # Compute cumulative token usage from all messages in history.
        # This is stored as a top-level attribute (not inside the encrypted blob) so that
        # list_sessions can surface it without needing to decrypt anything.
        total_tokens_used = 0
        for msg in request.messages:
            usage = msg.get("usage") or {}
            total_tokens_used += int(usage.get("completionTokens") or 0) + int(usage.get("promptTokens") or 0)

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
                    + "#encryption_version = :encryption_version, #is_encrypted = :is_encrypted, "
                    + "#totalTokensUsed = :totalTokensUsed",
                    ExpressionAttributeNames={
                        "#encrypted_history": "encrypted_history",
                        "#name": "name",
                        "#encrypted_configuration": "encrypted_configuration",
                        "#startTime": "startTime",
                        "#createTime": "createTime",
                        "#lastUpdated": "lastUpdated",
                        "#encryption_version": "encryption_version",
                        "#is_encrypted": "is_encrypted",
                        "#totalTokensUsed": "totalTokensUsed",
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
                        ":totalTokensUsed": total_tokens_used,
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
                + "#lastUpdated = :lastUpdated, #is_encrypted = :is_encrypted, "
                + "#totalTokensUsed = :totalTokensUsed",
                ExpressionAttributeNames={
                    "#history": "history",
                    "#name": "name",
                    "#configuration": "configuration",
                    "#startTime": "startTime",
                    "#createTime": "createTime",
                    "#lastUpdated": "lastUpdated",
                    "#is_encrypted": "is_encrypted",
                    "#totalTokensUsed": "totalTokensUsed",
                },
                ExpressionAttributeValues={
                    ":history": session_data.history,
                    ":name": session_data.name,
                    ":configuration": session_data.configuration.model_dump_for_storage(),
                    ":startTime": session_data.startTime,
                    ":createTime": session_data.createTime,
                    ":lastUpdated": session_data.lastUpdated,
                    ":is_encrypted": False,
                    ":totalTokensUsed": total_tokens_used,
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
                # Extract modelId from the session configuration if available
                model_id = None
                if configuration and configuration.selectedModel:
                    model_id = configuration.selectedModel.modelId

                metrics_event = MetricsEvent(
                    userId=user_id,
                    sessionId=session_id,
                    messages=session_data.history,
                    userGroups=groups,
                    timestamp=session_data.lastUpdated,
                    eventType="full",
                    modelId=model_id,
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


def _encode_cursor(last_evaluated_key: dict[str, Any]) -> str:
    """Encode a DynamoDB LastEvaluatedKey as a base64 cursor string."""
    # Convert Decimal values to int/float for JSON serialization
    serializable = convert_decimal(last_evaluated_key)
    return base64.urlsafe_b64encode(json.dumps(serializable).encode("utf-8")).decode("utf-8")


def _decode_cursor(cursor: str) -> dict[str, Any]:
    """Decode a base64 cursor string back to a DynamoDB ExclusiveStartKey."""
    decoded = json.loads(base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8"), parse_float=Decimal)
    # Ensure messageIndex is a Decimal (DynamoDB Number type)
    if "messageIndex" in decoded:
        decoded["messageIndex"] = Decimal(str(decoded["messageIndex"]))
    return decoded


@api_wrapper(max_request_size=MAX_LARGE_REQUEST_SIZE)
def post_messages(event: dict, context: dict) -> SuccessResponse | dict:
    """Append messages to a session in the messages table.

    This implements the incremental write pattern: only new messages are written,
    not the entire history. Also updates session metadata in the sessions table.
    """
    try:
        if not messages_table:
            return {"statusCode": 500, "body": json.dumps({"error": "Messages table not configured"})}

        user_id, _, groups = get_user_context(event)
        session_id = get_session_id(event)

        try:
            body = json.loads(event["body"], parse_float=Decimal)
        except json.JSONDecodeError as e:
            return {"statusCode": 400, "body": json.dumps({"error": f"Invalid JSON: {str(e)}"})}

        try:
            request = PostMessagesRequest.model_validate(body)
        except ValidationError as e:
            return {"statusCode": 400, "body": json.dumps({"error": str(e)})}

        if not request.messages:
            return {"statusCode": 400, "body": json.dumps({"error": "No messages provided"})}

        # Get configuration if provided
        configuration = request.configuration or SessionConfigurationModel()
        if configuration and configuration.selectedModel:
            configuration = _update_session_with_current_model_config(configuration)

        timestamp = iso_string()

        # Check if encryption is enabled
        encryption_enabled = _is_session_encryption_enabled()

        # Get current session to determine messageCount and whether migration is needed
        session_response = table.get_item(
            Key={"sessionId": session_id, "userId": user_id},
        )
        session_item = session_response.get("Item", {})
        current_storage_version = session_item.get("storageVersion", "1.0")
        current_message_count = int(session_item.get("messageCount", 0))

        # --- Lazy migration: if this is a legacy session, migrate existing history to messages table ---
        if current_storage_version != "2.0" and session_item.get("history"):
            logger.info(f"Migrating legacy session {session_id} to storageVersion 2.0")
            legacy_history = session_item["history"]

            # If session is encrypted, decrypt history first
            if session_item.get("is_encrypted", False):
                try:
                    decrypted_item = decrypt_session_fields(session_item, user_id, session_id)
                    legacy_history = decrypted_item.get("history", [])
                except SessionEncryptionError as e:
                    logger.error(f"Failed to decrypt legacy session for migration: {e}")
                    return {"statusCode": 500, "body": json.dumps({"error": "Failed to migrate session"})}

            # Write existing messages to the messages table
            migration_batch_items = []
            for i, msg in enumerate(legacy_history):
                message_item: dict[str, Any] = {
                    "sessionId": session_id,
                    "messageIndex": i,
                    "type": msg.get("type", "human"),
                    "createdAt": msg.get("createdAt") or session_item.get("startTime", timestamp),
                }
                content = msg.get("content")
                if encryption_enabled:
                    from utilities.session_encryption import encrypt_session_data as _encrypt
                    # Bundle content + metadata + reasoningContent into encrypted blob
                    sensitive_payload = {
                        "content": content,
                        "metadata": msg.get("metadata"),
                        "reasoningContent": msg.get("reasoningContent"),
                    }
                    message_item["content"] = _encrypt(sensitive_payload, user_id, session_id)
                    message_item["is_encrypted"] = True
                else:
                    message_item["content"] = content
                    if msg.get("metadata"):
                        message_item["metadata"] = msg["metadata"]
                    if msg.get("reasoningContent"):
                        message_item["reasoningContent"] = msg["reasoningContent"]
                # Non-sensitive operational fields always stored in plaintext
                if msg.get("toolCalls"):
                    message_item["toolCalls"] = msg["toolCalls"]
                if msg.get("usage"):
                    message_item["usage"] = msg["usage"]
                if msg.get("guardrailTriggered") is not None:
                    message_item["guardrailTriggered"] = msg["guardrailTriggered"]
                if msg.get("reasoningSignature"):
                    message_item["reasoningSignature"] = msg["reasoningSignature"]
                migration_batch_items.append({"PutRequest": {"Item": message_item}})

            # Write migration batch in chunks of 25
            for batch_start in range(0, len(migration_batch_items), 25):
                batch_chunk = migration_batch_items[batch_start : batch_start + 25]
                try:
                    resp = dynamodb.meta.client.batch_write_item(
                        RequestItems={messages_table.name: batch_chunk}
                    )
                    unprocessed = resp.get("UnprocessedItems", {})
                    retry_delay = 0.1
                    retries = 0
                    while unprocessed and retries < 5:
                        time.sleep(retry_delay)
                        resp = dynamodb.meta.client.batch_write_item(RequestItems=unprocessed)
                        unprocessed = resp.get("UnprocessedItems", {})
                        retry_delay = min(retry_delay * 2, 5)
                        retries += 1
                except ClientError as e:
                    logger.error(f"Failed to migrate messages for session {session_id}: {e}")
                    return {"statusCode": 500, "body": json.dumps({"error": "Failed to migrate session messages"})}

            # Update messageCount to reflect migrated messages
            current_message_count = len(legacy_history)

            # Remove the legacy history attribute from the sessions table
            try:
                remove_expr = "REMOVE #history"
                remove_names = {"#history": "history"}
                # Also remove encrypted fields if present
                if session_item.get("encrypted_history"):
                    remove_expr += ", #enc_history"
                    remove_names["#enc_history"] = "encrypted_history"
                table.update_item(
                    Key={"sessionId": session_id, "userId": user_id},
                    UpdateExpression=remove_expr,
                    ExpressionAttributeNames=remove_names,
                )
            except ClientError as e:
                logger.warning(f"Failed to remove legacy history for session {session_id}: {e}")

            logger.info(f"Successfully migrated {current_message_count} messages for session {session_id}")

        # Write messages to the messages table using BatchWriteItem
        # DynamoDB BatchWriteItem supports max 25 items per call
        new_messages = request.messages
        total_new_tokens = 0
        batch_items = []

        for i, msg in enumerate(new_messages):
            message_index = current_message_count + i
            usage = msg.get("usage") or {}
            total_new_tokens += int(usage.get("completionTokens") or 0) + int(usage.get("promptTokens") or 0)

            # Build the message item for DynamoDB
            message_item: dict[str, Any] = {
                "sessionId": session_id,
                "messageIndex": message_index,
                "type": msg.get("type", "human"),
                "createdAt": msg.get("createdAt") or timestamp,
            }

            # Store content (optionally encrypted)
            # When encryption is enabled, bundle content + metadata + reasoningContent
            # into a single encrypted blob (matching legacy behavior where these were
            # encrypted together under the history attribute)
            content = msg.get("content")
            if encryption_enabled:
                from utilities.session_encryption import encrypt_session_data

                # Build the sensitive payload to encrypt together
                sensitive_payload = {
                    "content": content,
                    "metadata": msg.get("metadata"),
                    "reasoningContent": msg.get("reasoningContent"),
                }
                message_item["content"] = encrypt_session_data(sensitive_payload, user_id, session_id)
                message_item["is_encrypted"] = True
            else:
                message_item["content"] = content
                # Store metadata and reasoningContent as plaintext only when not encrypted
                if msg.get("metadata"):
                    message_item["metadata"] = msg["metadata"]
                if msg.get("reasoningContent"):
                    message_item["reasoningContent"] = msg["reasoningContent"]

            # These fields are always stored in plaintext (non-sensitive operational data)
            if msg.get("toolCalls"):
                message_item["toolCalls"] = msg["toolCalls"]
            if msg.get("usage"):
                message_item["usage"] = msg["usage"]
            if msg.get("guardrailTriggered") is not None:
                message_item["guardrailTriggered"] = msg["guardrailTriggered"]
            if msg.get("reasoningSignature"):
                message_item["reasoningSignature"] = msg["reasoningSignature"]

            batch_items.append({"PutRequest": {"Item": message_item}})

        # Write in batches of 25 (DynamoDB limit)
        for batch_start in range(0, len(batch_items), 25):
            batch_chunk = batch_items[batch_start : batch_start + 25]
            try:
                response = dynamodb.meta.client.batch_write_item(
                    RequestItems={messages_table.name: batch_chunk}
                )
                # Handle unprocessed items with exponential backoff
                unprocessed = response.get("UnprocessedItems", {})
                retry_delay = 0.1
                retries = 0
                while unprocessed and retries < 5:
                    time.sleep(retry_delay)
                    response = dynamodb.meta.client.batch_write_item(RequestItems=unprocessed)
                    unprocessed = response.get("UnprocessedItems", {})
                    retry_delay = min(retry_delay * 2, 5)
                    retries += 1
            except ClientError as e:
                logger.error(f"Failed to write messages batch: {e}")
                return {"statusCode": 500, "body": json.dumps({"error": "Failed to write messages"})}

        # Update session metadata in the sessions table
        new_message_count = current_message_count + len(new_messages)

        # Build SET clause parts
        set_parts = [
            "#messageCount = :messageCount",
            "#lastUpdated = :lastUpdated",
            "#storageVersion = :storageVersion",
            "#createTime = if_not_exists(#createTime, :createTime)",
            "#startTime = if_not_exists(#startTime, :startTime)",
            "#is_encrypted = :is_encrypted",
        ]
        expression_attr_names = {
            "#messageCount": "messageCount",
            "#lastUpdated": "lastUpdated",
            "#storageVersion": "storageVersion",
            "#createTime": "createTime",
            "#startTime": "startTime",
            "#is_encrypted": "is_encrypted",
            "#totalTokensUsed": "totalTokensUsed",
        }
        expression_attr_values: dict[str, Any] = {
            ":messageCount": new_message_count,
            ":lastUpdated": timestamp,
            ":storageVersion": "2.0",
            ":createTime": timestamp,
            ":startTime": timestamp,
            ":is_encrypted": encryption_enabled,
            ":newTokens": total_new_tokens,
        }

        # Handle configuration storage — encrypt if encryption is enabled
        # Also track attributes to REMOVE (cleanup stale plaintext/encrypted fields)
        remove_parts = []
        if encryption_enabled:
            from utilities.session_encryption import encrypt_session_data as _encrypt_config
            encrypted_config = _encrypt_config(configuration.model_dump_for_storage(), user_id, session_id)
            set_parts.append("#encrypted_configuration = :encrypted_configuration")
            set_parts.append("#encryption_version = :encryption_version")
            expression_attr_names["#encrypted_configuration"] = "encrypted_configuration"
            expression_attr_names["#encryption_version"] = "encryption_version"
            expression_attr_values[":encrypted_configuration"] = encrypted_config
            expression_attr_values[":encryption_version"] = "1.0"
            # Remove stale plaintext configuration attribute
            remove_parts.append("#configuration")
            expression_attr_names["#configuration"] = "configuration"
        else:
            set_parts.append("#configuration = :configuration")
            expression_attr_names["#configuration"] = "configuration"
            expression_attr_values[":configuration"] = configuration.model_dump_for_storage()
            # Remove stale encrypted configuration attribute if transitioning from encrypted to unencrypted
            remove_parts.append("#encrypted_configuration")
            remove_parts.append("#encryption_version")
            expression_attr_names["#encrypted_configuration"] = "encrypted_configuration"
            expression_attr_names["#encryption_version"] = "encryption_version"

        # Add name if provided
        if request.name:
            set_parts.append("#name = :name")
            expression_attr_names["#name"] = "name"
            expression_attr_values[":name"] = request.name

        # Construct the full expression: SET ... ADD ... [REMOVE ...]
        update_expression = "SET " + ", ".join(set_parts) + " ADD #totalTokensUsed :newTokens"
        if remove_parts:
            update_expression += " REMOVE " + ", ".join(remove_parts)

        table.update_item(
            Key={"sessionId": session_id, "userId": user_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=expression_attr_names,
            ExpressionAttributeValues=expression_attr_values,
        )

        # Publish metrics for non-API-token users
        try:
            request_context = event.get("requestContext", {})
            authorizer_context = request_context.get("authorizer", {})
            auth_type = authorizer_context.get("authType", "jwt")

            if auth_type != "api_token" and "USAGE_METRICS_QUEUE_NAME" in os.environ:
                model_id = None
                if configuration and configuration.selectedModel:
                    model_id = configuration.selectedModel.modelId

                metrics_event = MetricsEvent(
                    userId=user_id,
                    sessionId=session_id,
                    messages=new_messages,
                    userGroups=groups,
                    timestamp=timestamp,
                    eventType="full",
                    modelId=model_id,
                )
                sqs_client.send_message(
                    QueueUrl=os.environ["USAGE_METRICS_QUEUE_NAME"],
                    MessageBody=json.dumps(convert_decimal(metrics_event.model_dump())),
                )
        except Exception as e:
            logger.error(f"Failed to publish metrics: {e}")

        return SuccessResponse(message=f"Successfully appended {len(new_messages)} messages")
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}


@api_wrapper
def get_messages(event: dict, context: dict) -> PaginatedMessagesResponse | dict:
    """Get paginated messages for a session using cursor-based pagination.

    Query parameters:
        - limit (int): Number of messages to return (default 50, max 200)
        - order (str): 'asc' or 'desc' (default 'desc' for newest first)
        - cursor (str): Opaque base64 cursor from previous response
    """
    try:
        if not messages_table:
            return {"statusCode": 500, "body": json.dumps({"error": "Messages table not configured"})}

        user_id = get_username(event)
        session_id = get_session_id(event)

        # Verify the user owns the session
        session_response = table.get_item(
            Key={"sessionId": session_id, "userId": user_id},
            ProjectionExpression="sessionId",
        )
        if not session_response.get("Item"):
            return {"statusCode": 404, "body": json.dumps({"error": "Session not found"})}

        # Parse query parameters
        query_params = event.get("queryStringParameters") or {}
        limit = min(int(query_params.get("limit", "50")), 200)
        order = query_params.get("order", "desc")
        cursor = query_params.get("cursor")

        # Build DynamoDB query
        query_kwargs: dict[str, Any] = {
            "KeyConditionExpression": "sessionId = :sid",
            "ExpressionAttributeValues": {":sid": session_id},
            "Limit": limit,
            "ScanIndexForward": (order == "asc"),
        }

        if cursor:
            try:
                query_kwargs["ExclusiveStartKey"] = _decode_cursor(cursor)
            except Exception as e:
                logger.warning(f"Invalid cursor: {e}")
                return {"statusCode": 400, "body": json.dumps({"error": "Invalid cursor"})}

        # Execute query
        response = messages_table.query(**query_kwargs)
        items = response.get("Items", [])
        last_evaluated_key = response.get("LastEvaluatedKey")

        # Decrypt content if encrypted
        for item in items:
            if item.get("is_encrypted") and item.get("content"):
                try:
                    from utilities.session_encryption import decrypt_session_data

                    decrypted = decrypt_session_data(item["content"], user_id, session_id)
                    # The encrypted blob contains {content, metadata, reasoningContent}
                    if isinstance(decrypted, dict) and "content" in decrypted:
                        item["content"] = decrypted["content"]
                        if decrypted.get("metadata"):
                            item["metadata"] = decrypted["metadata"]
                        if decrypted.get("reasoningContent"):
                            item["reasoningContent"] = decrypted["reasoningContent"]
                    else:
                        # Backward compat: older encrypted messages may have just content
                        item["content"] = decrypted
                    del item["is_encrypted"]
                except Exception as e:
                    logger.warning(f"Failed to decrypt message {item.get('messageIndex')}: {e}")

        # Generate presigned URLs for images/videos in messages
        image_tasks = []
        video_tasks = []
        for item in items:
            content = item.get("content")
            if isinstance(content, list):
                for content_item in content:
                    if isinstance(content_item, dict):
                        if content_item.get("type") == "image_url":
                            s3_key = content_item.get("image_url", {}).get("s3_key")
                            if s3_key:
                                image_tasks.append((content_item, s3_key))
                        elif content_item.get("type") == "video_url":
                            s3_key = content_item.get("video_url", {}).get("s3_key")
                            if s3_key:
                                video_tasks.append((content_item, s3_key))

        if image_tasks:
            list(executor.map(_process_image, image_tasks))
        if video_tasks:
            list(executor.map(_process_video, video_tasks))

        # Build response
        next_cursor = _encode_cursor(last_evaluated_key) if last_evaluated_key else None

        return PaginatedMessagesResponse(
            messages=items,
            nextCursor=next_cursor,
            hasMore=last_evaluated_key is not None,
        )
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}
