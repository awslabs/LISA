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

"""S3 metadata file manager for Bedrock KB documents."""

import json
import logging
from typing import Any, Dict, List, Tuple

from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds


class S3MetadataManager:
    """Manager for S3 metadata file operations."""

    def upload_metadata_file(
        self,
        s3_client,
        bucket: str,
        document_key: str,
        metadata_content: Dict[str, Any],
    ) -> str:
        """Upload metadata.json file to S3.

        Args:
            s3_client: Boto3 S3 client
            bucket: S3 bucket name
            document_key: S3 key of the document
            metadata_content: Metadata content dictionary

        Returns:
            S3 key of the uploaded metadata file

        Raises:
            ClientError: If S3 upload fails after retries
        """
        metadata_key = f"{document_key}.metadata.json"
        metadata_json = json.dumps(metadata_content, indent=2)

        logger.info(
            f"Uploading metadata file: s3://{bucket}/{metadata_key}",
            extra={
                "document_key": document_key,
                "metadata_key": metadata_key,
            },
        )

        # Upload with retries
        for attempt in range(MAX_RETRIES):
            try:
                s3_client.put_object(
                    Bucket=bucket,
                    Key=metadata_key,
                    Body=metadata_json.encode("utf-8"),
                    ContentType="application/json",
                )
                logger.info(f"Successfully uploaded metadata file: {metadata_key}")

                return metadata_key

            except ClientError as e:
                error_code = e.response["Error"]["Code"]

                # Don't retry on permission errors
                if error_code == "AccessDenied":
                    logger.error(f"Access denied uploading metadata file: {metadata_key}")
                    raise

                # Retry on transient errors
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Retry {attempt + 1}/{MAX_RETRIES} for metadata upload: {metadata_key}")
                    continue
                else:
                    logger.error(f"Failed to upload metadata file after {MAX_RETRIES} attempts: {metadata_key}")
                    raise

    def delete_metadata_file(
        self,
        s3_client,
        bucket: str,
        document_key: str,
    ) -> None:
        """Delete metadata.json file from S3.

        Args:
            s3_client: Boto3 S3 client
            bucket: S3 bucket name
            document_key: S3 key of the document

        Note:
            This operation is idempotent - no error if file doesn't exist
        """
        metadata_key = f"{document_key}.metadata.json"

        logger.info(
            f"Deleting metadata file: s3://{bucket}/{metadata_key}",
            extra={
                "document_key": document_key,
                "metadata_key": metadata_key,
            },
        )

        try:
            s3_client.delete_object(Bucket=bucket, Key=metadata_key)
            logger.info(f"Successfully deleted metadata file: {metadata_key}")

        except ClientError as e:
            error_code = e.response["Error"]["Code"]

            # Idempotent - file already deleted
            if error_code == "NoSuchKey":
                logger.info(f"Metadata file already deleted: {metadata_key}")
                return

            # Log other errors but don't fail
            logger.warning(f"Failed to delete metadata file: {metadata_key}, error: {e}")

    def batch_upload_metadata(self, s3_client, bucket: str, documents: List[Tuple[str, Dict[str, Any]]]) -> List[str]:
        """Upload multiple metadata files in batch.

        Args:
            s3_client: Boto3 S3 client
            bucket: S3 bucket name
            documents: List of (document_key, metadata_content) tuples

        Returns:
            List of successfully uploaded metadata file S3 keys
        """
        uploaded_keys = []
        failed_count = 0

        logger.info(f"Batch uploading {len(documents)} metadata files")

        for document_key, metadata_content in documents:
            try:
                metadata_key = self.upload_metadata_file(s3_client, bucket, document_key, metadata_content)
                uploaded_keys.append(metadata_key)
            except Exception as e:
                logger.error(f"Failed to upload metadata for {document_key}: {e}")
                failed_count += 1
                # Continue with other uploads

        logger.info(
            f"Batch upload complete: {len(uploaded_keys)} succeeded, {failed_count} failed out of {len(documents)}"
        )

        return uploaded_keys

    def batch_delete_metadata(self, s3_client, bucket: str, document_keys: List[str]) -> int:
        """Delete multiple metadata files in batch.

        Args:
            s3_client: Boto3 S3 client
            bucket: S3 bucket name
            document_keys: List of document S3 keys

        Returns:
            Number of successfully deleted metadata files
        """
        deleted_count = 0

        logger.info(f"Batch deleting {len(document_keys)} metadata files")

        for document_key in document_keys:
            try:
                self.delete_metadata_file(s3_client, bucket, document_key)
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete metadata for {document_key}: {e}")
                # Continue with other deletions

        logger.info(f"Batch delete complete: {deleted_count} deleted out of {len(document_keys)}")

        return deleted_count
