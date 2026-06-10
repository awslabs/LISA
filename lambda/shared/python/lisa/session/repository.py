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

"""Session data-access helpers shared across Lambda packages.

No module-level AWS resource instantiation — all clients/resources are
passed in by the caller so this module is safe to import from any Lambda
regardless of which environment variables are present.
"""

import logging
import os
import time
from typing import Any

from botocore.exceptions import ClientError
from lisa.domain.domain_objects import DeleteResponse
from lisa.utilities.session_encryption import (
    decrypt_session_data,
    decrypt_session_fields,
    encrypt_session_data,
    SessionEncryptionError,
)

logger = logging.getLogger(__name__)


def get_all_user_sessions(
    table: Any,
    user_id: str,
    projection_expression: str | None = None,
    expression_attribute_names: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """Return all sessions for a user, paginating as needed.

    Parameters
    ----------
    table:
        DynamoDB Table resource.
    user_id:
        Partition key value on the ``SESSIONS_BY_USER_ID_INDEX_NAME`` GSI.
    projection_expression:
        Optional DynamoDB ProjectionExpression. When supplied, DynamoDB
        returns only the listed attributes, dramatically reducing the
        response payload for list-style callers that do not need the full
        session history or configuration blobs.
    expression_attribute_names:
        Optional placeholder mapping used with reserved words in
        ``projection_expression`` (e.g. ``{"#n": "name"}``).
    """
    all_items: list[dict[str, Any]] = []
    exclusive_start_key: dict[str, Any] | None = None

    try:
        while True:
            query_params: dict[str, Any] = {
                "KeyConditionExpression": "userId = :user_id",
                "ExpressionAttributeValues": {":user_id": user_id},
                "IndexName": os.environ["SESSIONS_BY_USER_ID_INDEX_NAME"],
                "ScanIndexForward": False,
            }
            if projection_expression is not None:
                query_params["ProjectionExpression"] = projection_expression
            if expression_attribute_names is not None:
                query_params["ExpressionAttributeNames"] = expression_attribute_names
            if exclusive_start_key is not None:
                query_params["ExclusiveStartKey"] = exclusive_start_key

            response = table.query(**query_params)
            all_items.extend(response.get("Items", []))

            exclusive_start_key = response.get("LastEvaluatedKey")
            if exclusive_start_key is None:
                break
    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.warning(f"No sessions found for user {user_id}")
        else:
            logger.exception("Error listing sessions")
    return all_items


def extract_video_s3_keys(session: dict) -> list[str]:
    """Extract all video S3 keys from a session's history."""
    video_keys: list[str] = []
    for message in session.get("history", []):
        content = message.get("content")
        if isinstance(content, list):
            for item in content:
                if isinstance(item, dict) and item.get("type") == "video_url":
                    s3_key = item.get("video_url", {}).get("s3_key")
                    if s3_key:
                        video_keys.append(s3_key)
    return video_keys


def delete_session_messages(
    messages_table: Any,
    dynamodb_resource: Any,
    session_id: str,
) -> None:
    """Delete all messages for a session from the messages table."""
    if not messages_table:
        return

    try:
        # Query all message items for this session
        exclusive_start_key = None
        while True:
            query_params: dict[str, Any] = {
                "KeyConditionExpression": "sessionId = :sid",
                "ExpressionAttributeValues": {":sid": session_id},
                "ProjectionExpression": "sessionId, messageIndex",
            }
            if exclusive_start_key:
                query_params["ExclusiveStartKey"] = exclusive_start_key

            response = messages_table.query(**query_params)
            items = response.get("Items", [])

            # Delete in batches of 25. batch_write_item can return UnprocessedItems
            # (without raising) under throttling/partial failures, so loop on the
            # remaining items with exponential backoff.
            for batch_start in range(0, len(items), 25):
                batch_chunk = items[batch_start : batch_start + 25]
                pending_requests = [
                    {"DeleteRequest": {"Key": {"sessionId": item["sessionId"], "messageIndex": item["messageIndex"]}}}
                    for item in batch_chunk
                ]
                backoff_s = 0.1
                for attempt in range(5):
                    try:
                        resp = dynamodb_resource.meta.client.batch_write_item(
                            RequestItems={messages_table.name: pending_requests}
                        )
                    except ClientError as e:
                        logger.warning(f"Failed to delete message batch for session {session_id}: {e}")
                        break
                    pending_requests = (resp.get("UnprocessedItems") or {}).get(messages_table.name) or []
                    if not pending_requests:
                        break
                    if attempt < 4:
                        time.sleep(backoff_s)
                        backoff_s *= 2
                if pending_requests:
                    logger.error(
                        f"Gave up deleting {len(pending_requests)} message(s) for session {session_id} "
                        "after retries; orphan rows will remain."
                    )

            exclusive_start_key = response.get("LastEvaluatedKey")
            if not exclusive_start_key:
                break

        logger.info(f"Deleted all messages from messages table for session {session_id}")
    except ClientError as e:
        logger.warning(f"Error deleting messages for session {session_id}: {e}")


def delete_user_session(
    table: Any,
    s3_resource: Any,
    s3_client: Any,
    s3_bucket_name: str,
    session_id: str,
    user_id: str,
    messages_table: Any = None,
    dynamodb_resource: Any = None,
) -> DeleteResponse:
    """Delete a session from DynamoDB and clean up associated S3 objects and messages."""
    deleted = False
    try:
        response = table.get_item(Key={"sessionId": session_id, "userId": user_id})
        session = response.get("Item", {})

        if session.get("is_encrypted", False):
            try:
                logger.info(f"Decrypting session {session_id} to extract video keys for deletion")
                session = decrypt_session_fields(session, user_id, session_id)
            except SessionEncryptionError as e:
                logger.warning(f"Failed to decrypt session {session_id} for video cleanup: {e}")

        video_keys = extract_video_s3_keys(session)

        # Delete all messages from the messages table (if using storageVersion 2.0)
        if messages_table and dynamodb_resource:
            delete_session_messages(messages_table, dynamodb_resource, session_id)

        table.delete_item(Key={"sessionId": session_id, "userId": user_id})

        if s3_bucket_name:
            s3_resource.Bucket(s3_bucket_name).objects.filter(Prefix=f"images/{session_id}").delete()
            if video_keys:
                logger.info(f"Deleting {len(video_keys)} videos from S3 for session {session_id}")
                for video_key in video_keys:
                    try:
                        s3_client.delete_object(Bucket=s3_bucket_name, Key=video_key)
                    except ClientError as e:
                        logger.warning(f"Failed to delete video {video_key}: {e}")
        else:
            logger.warning(f"GENERATED_IMAGES_S3_BUCKET_NAME not set; skipping S3 cleanup for session {session_id}")

        deleted = True
    except ClientError as error:
        if error.response["Error"]["Code"] == "ResourceNotFoundException":
            logger.warning(f"No record found with session id: {session_id}")
        else:
            logger.exception("Error deleting session")
    return DeleteResponse(deleted=deleted)


# ---------------------------------------------------------------------------
# Storage version 2.0 — per-message helpers (formerly in session/lambda_functions.py).
# All boto3 resources are passed in by the caller; nothing is module-scoped.
# ---------------------------------------------------------------------------


def decrypt_message_in_place(msg: dict[str, Any], user_id: str, session_id: str) -> None:
    """Decrypt the bundled ``{content, metadata, reasoningContent}`` payload in-place.

    No-op when the message is not encrypted. On decrypt failure, logs and leaves
    the message untouched so callers can decide how to surface partial results.
    """
    if not (msg.get("is_encrypted") and msg.get("content")):
        return
    try:
        decrypted = decrypt_session_data(msg["content"], user_id, session_id)
        if isinstance(decrypted, dict) and "content" in decrypted:
            msg["content"] = decrypted["content"]
            if decrypted.get("metadata"):
                msg["metadata"] = decrypted["metadata"]
            if decrypted.get("reasoningContent"):
                msg["reasoningContent"] = decrypted["reasoningContent"]
        else:
            # Backward compat: older encrypted messages may have just content
            msg["content"] = decrypted
        msg.pop("is_encrypted", None)
    except Exception as e:
        logger.warning(f"Failed to decrypt message {msg.get('messageIndex')}: {e}")


def build_message_item(
    session_id: str,
    message_index: int,
    msg: dict[str, Any],
    encryption_enabled: bool,
    user_id: str,
    default_created_at: str,
) -> dict[str, Any]:
    """Build a message item ready to put into the messages table.

    Bundles ``{content, metadata, reasoningContent}`` into the encrypted blob
    when encryption is enabled; otherwise stores them as separate plaintext
    attributes. Operational fields (``toolCalls``, ``usage``,
    ``guardrailTriggered``, ``reasoningSignature``) are always plaintext.
    """
    item: dict[str, Any] = {
        "sessionId": session_id,
        "messageIndex": message_index,
        "type": msg.get("type", "human"),
        "createdAt": msg.get("createdAt") or default_created_at,
    }
    content = msg.get("content")
    if encryption_enabled:
        sensitive_payload = {
            "content": content,
            "metadata": msg.get("metadata"),
            "reasoningContent": msg.get("reasoningContent"),
        }
        item["content"] = encrypt_session_data(sensitive_payload, user_id, session_id)
        item["is_encrypted"] = True
    else:
        item["content"] = content
        if msg.get("metadata"):
            item["metadata"] = msg["metadata"]
        if msg.get("reasoningContent"):
            item["reasoningContent"] = msg["reasoningContent"]
    if msg.get("toolCalls"):
        item["toolCalls"] = msg["toolCalls"]
    if msg.get("usage"):
        item["usage"] = msg["usage"]
    if msg.get("guardrailTriggered") is not None:
        item["guardrailTriggered"] = msg["guardrailTriggered"]
    if msg.get("reasoningSignature"):
        item["reasoningSignature"] = msg["reasoningSignature"]
    return item


def put_message_with_index_retry(
    messages_table: Any,
    session_id: str,
    user_id: str,
    msg: dict[str, Any],
    encryption_enabled: bool,
    starting_index: int,
    default_created_at: str,
    max_attempts: int = 5,
) -> int:
    """Put a single message with ``attribute_not_exists(messageIndex)``.

    On collision, re-reads the current message count and retries at a higher
    index. Returns the messageIndex actually used. Raises ``ClientError`` on
    non-collision failure or ``RuntimeError`` after ``max_attempts`` collisions.
    """
    if messages_table is None:
        raise RuntimeError("messages_table must be configured")
    candidate_index = starting_index
    for attempt in range(max_attempts):
        item = build_message_item(session_id, candidate_index, msg, encryption_enabled, user_id, default_created_at)
        try:
            messages_table.put_item(Item=item, ConditionExpression="attribute_not_exists(messageIndex)")
            return candidate_index
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise
            count_resp = messages_table.query(
                KeyConditionExpression="sessionId = :sid",
                ExpressionAttributeValues={":sid": session_id},
                Select="COUNT",
            )
            current_count = int(count_resp.get("Count", 0))
            candidate_index = max(candidate_index + 1, current_count)
            logger.info(
                f"messageIndex collision for session {session_id} on attempt {attempt + 1}; "
                f"retrying at index {candidate_index}"
            )
    raise RuntimeError(f"Failed to assign unique messageIndex for session {session_id} after {max_attempts} attempts")


def query_session_messages(
    messages_table: Any,
    session_id: str,
    user_id: str,
    start_index: int | None = None,
) -> list[dict[str, Any]]:
    """Query messages for a session, ascending. Decrypts encrypted payloads in-place.

    When ``start_index`` is given, only messages with
    ``messageIndex >= start_index`` are returned.
    """
    if messages_table is None:
        raise RuntimeError("messages_table must be configured")
    all_msgs: list[dict[str, Any]] = []
    exclusive_start_key: dict[str, Any] | None = None
    if start_index is None:
        key_condition = "sessionId = :sid"
        attr_values: dict[str, Any] = {":sid": session_id}
    else:
        key_condition = "sessionId = :sid AND messageIndex >= :start"
        attr_values = {":sid": session_id, ":start": start_index}
    while True:
        query_params: dict[str, Any] = {
            "KeyConditionExpression": key_condition,
            "ExpressionAttributeValues": attr_values,
            "ScanIndexForward": True,
        }
        if exclusive_start_key:
            query_params["ExclusiveStartKey"] = exclusive_start_key
        resp = messages_table.query(**query_params)
        all_msgs.extend(resp.get("Items", []))
        exclusive_start_key = resp.get("LastEvaluatedKey")
        if not exclusive_start_key:
            break
    for msg in all_msgs:
        decrypt_message_in_place(msg, user_id, session_id)
    return all_msgs


def migrate_session_to_v2(
    table: Any,
    messages_table: Any,
    session_id: str,
    user_id: str,
    session_item: dict[str, Any],
    encryption_enabled: bool,
    timestamp: str,
) -> int:
    """Migrate a legacy (v1.0) session's history into the messages table.

    Idempotent: each per-message write is conditional on the sort key not
    existing, so a re-run after a partial failure is safe. Decrypts
    ``encrypted_history`` when present. Removes the legacy ``history`` /
    ``encrypted_history`` attributes from the session item only after all
    message writes succeed; only at that point is ``storageVersion`` flipped
    to 2.0, so readers always see either the v1 or v2 view, never a torn state.

    Returns the new messageCount.
    """
    if messages_table is None:
        raise RuntimeError("messages_table must be configured")

    legacy_history: list[dict[str, Any]] = session_item.get("history") or []

    # Decrypt encrypted_history if present (legacy encrypted sessions)
    if not legacy_history and session_item.get("encrypted_history"):
        try:
            decrypted_item = decrypt_session_fields(session_item, user_id, session_id)
            legacy_history = decrypted_item.get("history") or []
        except SessionEncryptionError as e:
            logger.error(f"Failed to decrypt legacy session for migration: {e}")
            raise

    if session_item.get("is_encrypted", False) and legacy_history and not session_item.get("encrypted_history"):
        # Belt-and-braces: encrypted sessions where history was already populated
        try:
            decrypted_item = decrypt_session_fields(session_item, user_id, session_id)
            legacy_history = decrypted_item.get("history") or legacy_history
        except SessionEncryptionError as e:
            logger.error(f"Failed to decrypt legacy session for migration: {e}")
            raise

    if not legacy_history:
        try:
            table.update_item(
                Key={"sessionId": session_id, "userId": user_id},
                UpdateExpression="SET #sv = :sv",
                ExpressionAttributeNames={"#sv": "storageVersion"},
                ExpressionAttributeValues={":sv": "2.0"},
            )
        except ClientError as e:
            logger.warning(f"Failed to set storageVersion 2.0 for empty legacy session {session_id}: {e}")
        return int(session_item.get("messageCount", 0))

    default_created_at = session_item.get("startTime") or timestamp
    for i, msg in enumerate(legacy_history):
        try:
            put_message_with_index_retry(
                messages_table=messages_table,
                session_id=session_id,
                user_id=user_id,
                msg=msg,
                encryption_enabled=encryption_enabled,
                starting_index=i,
                default_created_at=default_created_at,
                max_attempts=1,
            )
        except ClientError as e:
            logger.error(f"Failed to migrate message {i} for session {session_id}: {e}")
            raise
        except RuntimeError:
            # Index already populated — migration was previously partial; treat as success
            logger.info(f"Migration message at index {i} already exists for session {session_id}; skipping")

    remove_parts = ["#history"]
    remove_names = {"#history": "history"}
    if session_item.get("encrypted_history"):
        remove_parts.append("#enc_history")
        remove_names["#enc_history"] = "encrypted_history"
    try:
        table.update_item(
            Key={"sessionId": session_id, "userId": user_id},
            UpdateExpression="SET #sv = :sv REMOVE " + ", ".join(remove_parts),
            ExpressionAttributeNames={"#sv": "storageVersion", **remove_names},
            ExpressionAttributeValues={":sv": "2.0"},
        )
    except ClientError as e:
        logger.warning(f"Failed to finalize migration of session {session_id}: {e}")
        raise

    logger.info(f"Successfully migrated {len(legacy_history)} messages for session {session_id}")
    return len(legacy_history)
