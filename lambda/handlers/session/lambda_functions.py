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
from typing import Any, cast

import boto3
import create_env_variables  # noqa: F401
import requests as http_requests
from botocore.exceptions import ClientError
from cachetools import cached, TTLCache  # type: ignore[import-untyped,unused-ignore]
from lisa.domain.domain_objects import DeleteResponse, SuccessResponse
from lisa.metrics.models import MetricsEvent
from lisa.session.model_config import update_session_with_current_model_config
from lisa.session.models import (
    AttachImageRequest,
    CompactSessionRequest,
    CompactSessionResponse,
    PaginatedMessagesResponse,
    PostMessagesRequest,
    PutSessionRequest,
    RenameSessionRequest,
    Session,
    SessionConfigurationModel,
    SessionSummary,
)
from lisa.session.repository import (
    decrypt_message_in_place,
    delete_user_session,
    extract_video_s3_keys,
    get_all_user_sessions,
    migrate_session_to_v2,
    put_message_with_index_retry,
    query_session_messages,
)
from lisa.session.summarization import build_summary_prompt, format_messages_for_summary
from lisa.utilities.auth import get_user_context, get_username
from lisa.utilities.aws_helpers import get_cert_path, get_rest_api_container_endpoint
from lisa.utilities.common_functions import api_wrapper, get_session_id, retry_config
from lisa.utilities.encoders import convert_decimal
from lisa.utilities.input_validation import MAX_LARGE_REQUEST_SIZE
from lisa.utilities.pagination import decode_cursor, encode_cursor
from lisa.utilities.session_encryption import (
    decrypt_session_data,
    decrypt_session_fields,
    encrypt_session_data,
    is_session_encryption_enabled,
    migrate_session_to_encrypted,
    SessionEncryptionError,
)
from lisa.utilities.time import iso_string
from pydantic import ValidationError

logger = logging.getLogger(__name__)

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
s3_client = boto3.client("s3", region_name=os.environ["AWS_REGION"], config=retry_config)
s3_resource = boto3.resource("s3", region_name=os.environ["AWS_REGION"])
sqs_client = boto3.client("sqs", region_name=os.environ["AWS_REGION"], config=retry_config)
table = dynamodb.Table(os.environ["SESSIONS_TABLE_NAME"])
messages_table = dynamodb.Table(os.environ["MESSAGES_TABLE_NAME"]) if os.environ.get("MESSAGES_TABLE_NAME") else None
projects_table = dynamodb.Table(os.environ["PROJECTS_TABLE_NAME"]) if os.environ.get("PROJECTS_TABLE_NAME") else None

# Attributes required to build a `SessionSummary` and extract the first human
# message preview. Deliberately excludes `configuration` and
# `encrypted_configuration`, which can be large and aren't needed to render
# the session sidebar. Aliased via ExpressionAttributeNames because `name` is
# a DynamoDB reserved word.
_LIST_SESSIONS_PROJECTION_EXPRESSION = (
    "sessionId, userId, #n, projectId, startTime, createTime, lastUpdated, "
    "is_encrypted, history, encrypted_history, totalTokensUsed, compactionMessageIndex, "
    "tokensUsedSinceCompaction"
)
_LIST_SESSIONS_ATTRIBUTE_NAMES = {"#n": "name"}
s3_bucket_name = os.environ.get("GENERATED_IMAGES_S3_BUCKET_NAME", "")

# Get model table for real-time feature validation
model_table = dynamodb.Table(os.environ["MODEL_TABLE_NAME"]) if os.environ.get("MODEL_TABLE_NAME") else None

# Get configuration table for system settings
config_table = dynamodb.Table(os.environ["CONFIG_TABLE_NAME"])

executor = ThreadPoolExecutor(max_workers=10)

# Cache the encryption-enabled result for 5 minutes to avoid hammering the config table on every request.
_encryption_cache: TTLCache = TTLCache(maxsize=1, ttl=300)


@cached(cache=_encryption_cache)
def _is_session_encryption_enabled() -> Any:
    """Thin wrapper around the shared helper, bound to this module's config table."""
    return is_session_encryption_enabled(config_table)


def _update_session_with_current_model_config(
    session_config: SessionConfigurationModel,
) -> SessionConfigurationModel:
    """Thin wrapper bound to this module's model table."""
    return update_session_with_current_model_config(session_config, model_table)


def _get_all_user_sessions(user_id: str) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], get_all_user_sessions(table, user_id))


def _get_user_sessions_for_listing(user_id: str) -> list[dict[str, Any]]:
    """Fetch the caller's sessions projected to just the attributes needed for
    ``list_sessions``. Skips heavy fields like ``configuration`` /
    ``encrypted_configuration`` to keep the DynamoDB → Lambda payload small.
    """
    return cast(
        list[dict[str, Any]],
        get_all_user_sessions(
            table,
            user_id,
            projection_expression=_LIST_SESSIONS_PROJECTION_EXPRESSION,
            expression_attribute_names=_LIST_SESSIONS_ATTRIBUTE_NAMES,
        ),
    )


def _delete_user_session(session_id: str, user_id: str) -> DeleteResponse:
    return delete_user_session(
        table,
        s3_resource,
        s3_client,
        s3_bucket_name,
        session_id,
        user_id,
        messages_table=messages_table,
        dynamodb_resource=dynamodb,
    )


def _extract_video_s3_keys(session: dict) -> list[str]:
    return cast(list[str], extract_video_s3_keys(session))


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
    # Resolve dangling projectId: treat as None if not in the validated set.
    # Compare using str() so DynamoDB number types and str ids match the validation set.
    resolved_project_id: str | None = None
    if raw_project_id is not None and valid_project_ids is not None:
        if str(raw_project_id) in valid_project_ids:
            resolved_project_id = str(raw_project_id)
    raw_tokens = session.get("totalTokensUsed")
    total_tokens_used = int(raw_tokens) if raw_tokens is not None else None
    raw_compactionMessageIndex = session.get("compactionMessageIndex")
    compaction_message_index = int(raw_compactionMessageIndex) if raw_compactionMessageIndex is not None else None
    raw_tokensUsedSinceCompaction = session.get("tokensUsedSinceCompaction")
    tokens_used_since_compaction = (
        int(raw_tokensUsedSinceCompaction) if raw_tokensUsedSinceCompaction is not None else None
    )
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
        compactionMessageIndex=compaction_message_index,
        tokensUsedSinceCompaction=tokens_used_since_compaction,
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
                    decrypt_message_in_place(msg_item, user_id, session_id)
                    content = msg_item.get("content")
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
                logging.info(f"Decrypting encrypted session {session_id} " f"to find first message for user {user_id}")
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
                        text = item.get("text", "")
                        if text:
                            cleaned = _strip_context_from_display_text(text)
                            if cleaned:
                                return cleaned
            else:
                logger.warning(f"Unhandled human message content in session {session_id}")
    return ""


def _valid_project_ids_via_get_item(projects: Any, user_id: str, project_ids: set[str]) -> set[str]:
    """Return project IDs that exist for this user and are not status ``deleting``."""
    # Use the Table resource’s ``get_item`` (not low-level ``batch_get_item``): it shares
    # the same endpoint as other table operations, behaves consistently in moto, and
    # avoids import-time / client scoping issues in tests.
    valid: set[str] = set()
    for pid in project_ids:
        try:
            resp = projects.get_item(
                Key={"userId": user_id, "projectId": pid},
                ProjectionExpression="projectId, #s",
                ExpressionAttributeNames={"#s": "status"},
            )
            item = resp.get("Item")
            if not item:
                continue
            if item.get("status") == "deleting":
                continue
            valid.add(str(item.get("projectId", pid)))
        except Exception as e:  # noqa: BLE001 - validate best-effort per id
            logger.warning("get_item for project %s validation failed: %s", pid, e)
    return valid


@api_wrapper
def list_sessions(event: dict, context: dict) -> list[SessionSummary]:
    """List sessions by user ID from DynamoDB."""
    user_id = get_username(event)

    logger.info(f"Listing sessions for user {user_id}")
    sessions = _get_user_sessions_for_listing(user_id)

    valid_project_ids: set[str] = set()
    if projects_table is not None:
        unique_project_ids = {str(s["projectId"]) for s in sessions if s.get("projectId")}
        if unique_project_ids:
            try:
                valid_project_ids = _valid_project_ids_via_get_item(projects_table, user_id, unique_project_ids)
            except Exception as e:
                logger.warning(f"Project id validation failed: {e}")

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
                    config_data = decrypt_session_data(item["encrypted_configuration"], user_id, session_id)
                except Exception as e:
                    logger.warning(f"Failed to decrypt configuration for session {session_id}: {e}")
                    config_data = None

            # Build Session object from metadata (no history in the item)
            raw_cmi = item.get("compactionMessageIndex")
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
                compactionMessageIndex=int(raw_cmi) if raw_cmi is not None else None,
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
            next_cursor = encode_cursor(last_evaluated_key) if has_more else None

            # Decrypt message content if encrypted
            for msg_item in all_messages:
                decrypt_message_in_place(msg_item, user_id, session_id)

            session = session.model_copy(
                update={
                    "history": all_messages,
                    "nextCursor": next_cursor,
                    "hasMoreMessages": has_more,
                }
            )
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

        # Replace S3 keys with presigned URLs in image/video content blocks
        _attach_presigned_urls(list(session.history))
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

        # Detect storage version of the existing record. v2.0 sessions store history in
        # the messages table — put_session must NOT touch history/encrypted_history or
        # recompute totalTokensUsed (post_messages already increments it atomically).
        existing_resp = table.get_item(
            Key={"sessionId": session_id, "userId": user_id},
            ProjectionExpression="storageVersion",
            ConsistentRead=True,
        )
        existing_storage_version = existing_resp.get("Item", {}).get("storageVersion", "1.0")
        is_v2_session = existing_storage_version == "2.0"

        # v2.0 path: metadata-only update. Skip history writes, token recompute, and
        # the metrics SQS publish (per-message metrics already flow through post_messages).
        if is_v2_session:
            timestamp = iso_string()
            set_parts = [
                "#name = :name",
                "#lastUpdated = :lastUpdated",
                "#is_encrypted = :is_encrypted",
            ]
            expression_attr_names: dict[str, str] = {
                "#name": "name",
                "#lastUpdated": "lastUpdated",
                "#is_encrypted": "is_encrypted",
            }
            expression_attr_values: dict[str, Any] = {
                ":name": request.name,
                ":lastUpdated": timestamp,
                ":is_encrypted": encryption_enabled,
            }
            remove_parts: list[str] = []
            if encryption_enabled:
                encrypted_config = encrypt_session_data(configuration.model_dump_for_storage(), user_id, session_id)
                set_parts.append("#encrypted_configuration = :encrypted_configuration")
                set_parts.append("#encryption_version = :encryption_version")
                expression_attr_names["#encrypted_configuration"] = "encrypted_configuration"
                expression_attr_names["#encryption_version"] = "encryption_version"
                expression_attr_values[":encrypted_configuration"] = encrypted_config
                expression_attr_values[":encryption_version"] = "1.0"
                remove_parts.append("#configuration")
                expression_attr_names["#configuration"] = "configuration"
            else:
                set_parts.append("#configuration = :configuration")
                expression_attr_names["#configuration"] = "configuration"
                expression_attr_values[":configuration"] = configuration.model_dump_for_storage()
                remove_parts.append("#encrypted_configuration")
                remove_parts.append("#encryption_version")
                expression_attr_names["#encrypted_configuration"] = "encrypted_configuration"
                expression_attr_names["#encryption_version"] = "encryption_version"
            update_expression = "SET " + ", ".join(set_parts)
            if remove_parts:
                update_expression += " REMOVE " + ", ".join(remove_parts)
            table.update_item(
                Key={"sessionId": session_id, "userId": user_id},
                UpdateExpression=update_expression,
                ExpressionAttributeNames=expression_attr_names,
                ExpressionAttributeValues=expression_attr_values,
            )
            return SuccessResponse(message="Session updated successfully")

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


def _attach_presigned_urls(messages: list[dict[str, Any]]) -> None:
    """Walk message content blocks and replace S3 keys with presigned URLs in-place."""
    image_tasks: list[tuple[dict, str]] = []
    video_tasks: list[tuple[dict, str]] = []
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for content_item in content:
            if not isinstance(content_item, dict):
                continue
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

        # Get configuration if provided. Keep `None` when the caller didn't send one
        # so we leave the existing stored configuration untouched
        configuration = request.configuration
        if configuration is not None and configuration.selectedModel:
            configuration = _update_session_with_current_model_config(configuration)

        timestamp = iso_string()

        # Check if encryption is enabled
        encryption_enabled = _is_session_encryption_enabled()

        # Get current session to determine messageCount and whether migration is needed.
        session_response = table.get_item(
            Key={"sessionId": session_id, "userId": user_id},
            ConsistentRead=True,
        )
        session_item = session_response.get("Item", {})
        current_storage_version = session_item.get("storageVersion", "1.0")
        current_message_count = int(session_item.get("messageCount", 0))

        # Lazy migration: if this is a legacy session, migrate existing history to messages table
        # Catches both plaintext (`history`) and encrypted (`encrypted_history`) legacy sessions.
        if current_storage_version != "2.0" and (session_item.get("history") or session_item.get("encrypted_history")):
            logger.info(f"Migrating legacy session {session_id} to storageVersion 2.0")
            try:
                migrated_count = migrate_session_to_v2(
                    table, messages_table, session_id, user_id, session_item, encryption_enabled, timestamp
                )
            except SessionEncryptionError:
                return {"statusCode": 500, "body": json.dumps({"error": "Failed to migrate session"})}
            except ClientError:
                return {"statusCode": 500, "body": json.dumps({"error": "Failed to migrate session messages"})}
            current_message_count = migrated_count

        # Write new messages
        new_messages = request.messages
        total_new_tokens = 0
        next_index = current_message_count
        for msg in new_messages:
            usage = msg.get("usage") or {}
            total_new_tokens += int(usage.get("completionTokens") or 0) + int(usage.get("promptTokens") or 0)
            try:
                assigned_index = put_message_with_index_retry(
                    messages_table=messages_table,
                    session_id=session_id,
                    user_id=user_id,
                    msg=msg,
                    encryption_enabled=encryption_enabled,
                    starting_index=next_index,
                    default_created_at=timestamp,
                )
            except (ClientError, RuntimeError) as e:
                logger.error(f"Failed to write message at index {next_index} for session {session_id}: {e}")
                return {"statusCode": 500, "body": json.dumps({"error": "Failed to write messages"})}
            next_index = assigned_index + 1

        # Update session metadata in the sessions table.
        delta_messages = len(new_messages)
        set_parts = [
            "#lastUpdated = :lastUpdated",
            "#storageVersion = if_not_exists(#storageVersion, :storageVersion)",
            "#createTime = if_not_exists(#createTime, :createTime)",
            "#startTime = if_not_exists(#startTime, :startTime)",
            "#is_encrypted = :is_encrypted",
        ]
        expression_attr_names = {
            "#lastUpdated": "lastUpdated",
            "#storageVersion": "storageVersion",
            "#createTime": "createTime",
            "#startTime": "startTime",
            "#is_encrypted": "is_encrypted",
            "#totalTokensUsed": "totalTokensUsed",
            "#tokensUsedSinceCompaction": "tokensUsedSinceCompaction",
            "#messageCount": "messageCount",
        }
        expression_attr_values: dict[str, Any] = {
            ":lastUpdated": timestamp,
            ":storageVersion": "2.0",
            ":createTime": timestamp,
            ":startTime": timestamp,
            ":is_encrypted": encryption_enabled,
            ":newTokens": total_new_tokens,
            ":deltaMessages": delta_messages,
        }

        # Handle configuration storage — encrypt if encryption is enabled.
        # When the caller did NOT send a configuration block, skip the configuration
        # update entirely so an append-only request doesn't clobber existing config.
        # Also track attributes to REMOVE (cleanup stale plaintext/encrypted fields).
        remove_parts = []
        if configuration is not None:
            if encryption_enabled:
                encrypted_config = encrypt_session_data(configuration.model_dump_for_storage(), user_id, session_id)
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

        update_expression = (
            "SET "
            + ", ".join(set_parts)
            + " ADD #totalTokensUsed :newTokens, #tokensUsedSinceCompaction :newTokens, "
            + "#messageCount :deltaMessages"
        )
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

        # Parse query parameters. Clamp `limit` into [1, 200] — DynamoDB rejects
        # zero/negative values with a ParamValidationError that would otherwise
        # surface as a 500. Reject non-numeric input with 400.
        query_params = event.get("queryStringParameters") or {}
        try:
            requested_limit = int(query_params.get("limit", "50"))
        except (TypeError, ValueError):
            return {"statusCode": 400, "body": json.dumps({"error": "Invalid limit"})}
        limit = max(1, min(requested_limit, 200))
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
                query_kwargs["ExclusiveStartKey"] = decode_cursor(cursor)
            except Exception as e:
                logger.warning(f"Invalid cursor: {e}")
                return {"statusCode": 400, "body": json.dumps({"error": "Invalid cursor"})}

        # Execute query
        response = messages_table.query(**query_kwargs)
        items = response.get("Items", [])
        last_evaluated_key = response.get("LastEvaluatedKey")

        # Decrypt content if encrypted
        for item in items:
            decrypt_message_in_place(item, user_id, session_id)

        # Generate presigned URLs for images/videos in messages
        _attach_presigned_urls(items)

        # Build response
        next_cursor = encode_cursor(last_evaluated_key) if last_evaluated_key else None

        return PaginatedMessagesResponse(
            messages=items,
            nextCursor=next_cursor,
            hasMore=last_evaluated_key is not None,
        )
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}


@api_wrapper
def compact_session(event: dict, context: dict) -> CompactSessionResponse | dict:
    """Compact a session by summarizing older messages into a SUMMARY message.

    When token usage approaches the context window limit, this endpoint summarizes
    older messages so subsequent LLM calls use a bounded context. The summary is
    written as a new message with type 'summary' and the session's
    compactionMessageIndex is updated to point to it.
    """
    try:
        if not messages_table:
            return {"statusCode": 500, "body": json.dumps({"error": "Messages table not configured"})}

        user_id = get_username(event)
        session_id = get_session_id(event)

        try:
            body = json.loads(event["body"], parse_float=Decimal)
        except json.JSONDecodeError as e:
            return {"statusCode": 400, "body": json.dumps({"error": f"Invalid JSON: {str(e)}"})}

        try:
            request = CompactSessionRequest.model_validate(body)
        except ValidationError as e:
            return {"statusCode": 400, "body": json.dumps({"error": str(e)})}

        # 1. Verify session ownership and get current state
        session_response = table.get_item(
            Key={"sessionId": session_id, "userId": user_id},
            ConsistentRead=True,
        )
        session_item = session_response.get("Item", {})
        if not session_item:
            return {"statusCode": 404, "body": json.dumps({"error": "Session not found"})}

        encryption_enabled = _is_session_encryption_enabled()
        timestamp_for_migration = iso_string()
        storage_version = session_item.get("storageVersion", "1.0")

        # Auto-migrate legacy sessions instead of returning 400. So a user
        # with a long pre-existing session can compact on the very next send,
        # without needing post_messages to run first.
        if storage_version != "2.0":
            try:
                migrated_count = migrate_session_to_v2(
                    table,
                    messages_table,
                    session_id,
                    user_id,
                    session_item,
                    encryption_enabled,
                    timestamp_for_migration,
                )
            except SessionEncryptionError:
                return {"statusCode": 500, "body": json.dumps({"error": "Failed to migrate session"})}
            except ClientError:
                return {"statusCode": 500, "body": json.dumps({"error": "Failed to migrate session messages"})}
            session_item["storageVersion"] = "2.0"
            session_item["messageCount"] = migrated_count

        current_message_count = int(session_item.get("messageCount", 0))
        current_compaction_index = session_item.get("compactionMessageIndex")

        # If messageCount is not tracked, derive it from messages table
        if current_message_count == 0:
            count_resp = messages_table.query(
                KeyConditionExpression="sessionId = :sid",
                ExpressionAttributeValues={":sid": session_id},
                Select="COUNT",
            )
            current_message_count = count_resp.get("Count", 0)

        # 2. Guard: need at least 3 messages (system + 1 exchange)
        if current_message_count < 3:
            return {"statusCode": 400, "body": json.dumps({"error": "Session too short to compact"})}

        # 3. Load all messages (decrypted) using the shared helper
        all_messages = query_session_messages(messages_table, session_id, user_id)

        # 4. Determine summarization range. Exclude the prior summary
        if current_compaction_index is not None:
            summarize_start = int(current_compaction_index) + 1
        else:
            # First compaction: skip index 0 (system message)
            summarize_start = 1

        messages_for_summary = [m for m in all_messages if int(m["messageIndex"]) >= summarize_start]

        if not messages_for_summary:
            return {"statusCode": 400, "body": json.dumps({"error": "No messages available for compaction"})}

        # 6. Format messages and build prompt
        conversation_text = format_messages_for_summary(messages_for_summary)
        summary_prompt = build_summary_prompt(conversation_text)

        # 7. Call serve API
        serve_endpoint = get_rest_api_container_endpoint()
        headers = event.get("headers") or {}
        auth_token = headers.get("Authorization", "") or headers.get("authorization", "")

        iam_client = boto3.client("iam", region_name=os.environ["AWS_REGION"])
        cert_path = get_cert_path(iam_client)

        llm_response = http_requests.post(
            f"{serve_endpoint}/chat/completions",
            headers={
                "Authorization": auth_token,
                "Content-Type": "application/json",
            },
            json={
                "model": request.modelId,
                "messages": [
                    {"role": "system", "content": "You are a precise conversation summarizer."},
                    {"role": "user", "content": summary_prompt},
                ],
                "max_tokens": 4096,
                "temperature": 0.0,
            },
            verify=cert_path,
            timeout=120,
        )

        if llm_response.status_code != 200:
            logger.error(f"Summarization call failed with status {llm_response.status_code}: {llm_response.text}")
            return {"statusCode": 502, "body": json.dumps({"error": "Summarization call failed"})}

        # Validate the LLM response A 200 with a malformed body should NOT advance compactionMessageIndex
        # or persist an empty SUMMARY — that would erase all prior context.
        try:
            response_data = llm_response.json()
        except ValueError:
            logger.error(f"Summarization returned invalid JSON: {llm_response.text!r}")
            return {"statusCode": 502, "body": json.dumps({"error": "Summarization returned invalid JSON"})}

        choices = response_data.get("choices") if isinstance(response_data, dict) else None
        summary_content_raw: Any = None
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            if isinstance(first_choice, dict):
                summary_content_raw = (first_choice.get("message") or {}).get("content")
        if not isinstance(summary_content_raw, str) or not summary_content_raw.strip():
            logger.error(f"Summarization returned empty/invalid content: {response_data!r}")
            return {"statusCode": 502, "body": json.dumps({"error": "Summarization returned empty content"})}
        summary_content = summary_content_raw.strip()

        # 8. Write SUMMARY to messages table
        timestamp = iso_string()
        summary_msg = {"type": "summary", "content": summary_content}
        summary_message_index = put_message_with_index_retry(
            messages_table=messages_table,
            session_id=session_id,
            user_id=user_id,
            msg=summary_msg,
            encryption_enabled=encryption_enabled,
            starting_index=current_message_count,
            default_created_at=timestamp,
        )

        # Extract system prompt from the already-loaded messages
        system_prompt = ""
        if all_messages:
            first_msg = all_messages[0]
            content = first_msg.get("content", "")
            if isinstance(content, str):
                system_prompt = content
            elif isinstance(content, list):
                system_prompt = " ".join(item.get("text", "") for item in content if isinstance(item, dict))

        # Build the compacted system prompt — persisted on the session item so other
        # consumers (and the client, which mirrors this format) can reconstruct it.
        compacted_system_prompt = f"{system_prompt}\n\n--- Conversation Summary (prior context) ---\n{summary_content}"

        # 9. Update sessions table
        table.update_item(
            Key={"sessionId": session_id, "userId": user_id},
            UpdateExpression=(
                "SET #cmi = :cmi, #lastUpdated = :lastUpdated, "
                "#tokensUsedSinceCompaction = :zero, #csp = :csp "
                "ADD #mc :one"
            ),
            ExpressionAttributeNames={
                "#cmi": "compactionMessageIndex",
                "#mc": "messageCount",
                "#lastUpdated": "lastUpdated",
                "#tokensUsedSinceCompaction": "tokensUsedSinceCompaction",
                "#csp": "compactedSystemPrompt",
            },
            ExpressionAttributeValues={
                ":cmi": summary_message_index,
                ":lastUpdated": timestamp,
                ":zero": 0,
                ":csp": compacted_system_prompt,
                ":one": 1,
            },
        )

        logger.info(
            f"Session {session_id} compacted: summary at index {summary_message_index}, "
            f"summarized {len(messages_for_summary)} messages starting at index {summarize_start}"
        )

        return CompactSessionResponse(
            summaryMessageIndex=summary_message_index,
            summaryContent=summary_content,
            compactionMessageIndex=summary_message_index,
            systemPrompt=system_prompt,
        )
    except ValueError as e:
        return {"statusCode": 400, "body": json.dumps({"error": str(e)})}
    except Exception as e:
        logger.error(f"Compaction failed for session: {e}", exc_info=True)
        return {"statusCode": 500, "body": json.dumps({"error": f"Compaction failed: {str(e)}"})}
