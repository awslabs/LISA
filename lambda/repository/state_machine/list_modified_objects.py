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

"""Lambda handlers for ListModifiedObjects state machine."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import boto3
from utilities.validation import safe_error_response, ValidationError

logger = logging.getLogger(__name__)


def normalize_prefix(prefix: str) -> str:
    """
    Normalize the S3 prefix by handling trailing slashes.

    Args:
        prefix: S3 prefix to normalize

    Returns:
        Normalized prefix
    """
    if not prefix:
        return ""

    # Remove leading/trailing slashes and spaces
    prefix = prefix.strip().strip("/")

    # If prefix is not empty, ensure it ends with a slash
    if prefix:
        prefix = f"{prefix}/"

    return prefix


def validate_bucket_prefix(bucket: str, prefix: str) -> bool:
    """
    Validate bucket and prefix parameters.

    Args:
        bucket: S3 bucket name
        prefix: S3 prefix

    Returns:
        bool: True if valid

    Raises:
        ValidationError: If parameters are invalid
    """
    if not bucket or not isinstance(bucket, str):
        raise ValidationError(f"Invalid bucket name: {bucket}")

    if prefix is None or not isinstance(prefix, str):
        raise ValidationError(f"Invalid prefix: {prefix}")

    # Basic path traversal check
    if ".." in prefix:
        raise ValidationError(f"Invalid prefix: path traversal detected in {prefix}")

    return True


def handle_list_modified_objects(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Lists all objects in the specified S3 bucket and prefix that were modified in the last 24 hours.

    Args:
        event: Event data containing bucket and prefix information
        context: Lambda context

    Returns:
        Dictionary containing array of files with their bucket and key
    """
    try:
        # Log the full event for debugging
        logger.debug(f"Received event: {event}")

        # Extract bucket and prefix from event, handling both event types
        detail = event.get("detail", {})

        # Handle both direct bucket name and nested bucket structure
        bucket = detail.get("bucket")
        if isinstance(bucket, dict):
            bucket = bucket.get("name")

        # For event triggers, use the object key as prefix if no prefix specified
        prefix = detail.get("prefix")
        if not prefix and "object" in detail:
            prefix = detail["object"].get("key", "")

        # Normalize the prefix
        prefix = normalize_prefix(prefix)

        # Add debug logging
        logger.info(f"Processing request for bucket: {bucket}, normalized prefix: {prefix}")

        # Validate inputs
        validate_bucket_prefix(bucket, prefix)

        # Initialize S3 client
        s3_client = boto3.client("s3")

        # Calculate timestamp for 24 hours ago
        twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)

        # List to store matching objects
        modified_files = []

        # Use paginator to handle case where there are more than 1000 objects
        paginator = s3_client.get_paginator("list_objects_v2")

        # Add debug logging for S3 list operation
        logger.info(f"Listing objects in {bucket}/{prefix} modified after {twenty_four_hours_ago}")

        # Iterate through all objects in the bucket/prefix
        try:
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                if "Contents" not in page:
                    logger.info(f"No contents found in page for {bucket}/{prefix}")
                    continue

                # Check each object's last modified time
                for obj in page["Contents"]:
                    last_modified = obj["LastModified"]
                    if last_modified >= twenty_four_hours_ago:
                        logger.info(f"Found modified file: {obj['Key']} (Last Modified: {last_modified})")
                        modified_files.append({"bucket": bucket, "key": obj["Key"]})
                    else:
                        logger.debug(
                            f"Skipping file {obj['Key']} - Last modified {last_modified} before cutoff "
                            f"{twenty_four_hours_ago}"
                        )
        except Exception as e:
            logger.error(f"Error during S3 list operation: {str(e)}", exc_info=True)
            raise

        result = {
            "files": modified_files,
            "metadata": {
                "bucket": bucket,
                "prefix": prefix,
                "cutoff_time": twenty_four_hours_ago.isoformat(),
                "files_found": len(modified_files),
            },
        }

        logger.info(f"Found {len(modified_files)} modified files in {bucket}/{prefix}")
        return result

    except ValidationError as e:
        logger.error(f"Validation error: {str(e)}")
        return safe_error_response(e)
    except Exception as e:
        logger.error(f"Error listing objects: {str(e)}", exc_info=True)
        return safe_error_response(e)
