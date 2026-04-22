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
from typing import Any

from botocore.exceptions import ClientError
from models.domain_objects import DeleteResponse
from utilities.session_encryption import decrypt_session_fields, SessionEncryptionError

logger = logging.getLogger(__name__)


def get_all_user_sessions(
    table: Any,
    user_id: str,
) -> list[dict[str, Any]]:
    """Return all sessions for a user, paginating as needed."""
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


def delete_user_session(
    table: Any,
    s3_resource: Any,
    s3_client: Any,
    s3_bucket_name: str,
    session_id: str,
    user_id: str,
) -> DeleteResponse:
    """Delete a session from DynamoDB and clean up associated S3 objects."""
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
