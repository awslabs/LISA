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

"""Metadata generator for Bedrock KB documents."""

import json
import logging
import re
import time
from typing import Any, Dict, Optional

import boto3
from models.domain_objects import CollectionMetadata, RagCollectionConfig
from utilities.validation import ValidationError

logger = logging.getLogger(__name__)

# Bedrock KB metadata limits
MAX_METADATA_SIZE_BYTES = 10240  # 10KB
MAX_METADATA_KEY_LENGTH = 100
MAX_METADATA_VALUE_LENGTH = 1000

# Reserved Bedrock KB field names
RESERVED_FIELDS = {
    "x-amz-bedrock-kb-source-uri",
    "x-amz-bedrock-kb-data-source-id",
    "x-amz-bedrock-kb-chunk-id",
}


class MetadataGenerator:
    """Generator for Bedrock KB metadata files."""

    def __init__(self, cloudwatch_client=None):
        """Initialize metadata generator with caching.

        Args:
            cloudwatch_client: Optional CloudWatch client for metrics (defaults to creating one)
        """
        self._collection_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 300  # 5 minutes
        self.cloudwatch_client = cloudwatch_client or boto3.client("cloudwatch")

    def _emit_metric(
        self,
        metric_name: str,
        value: float = 1.0,
        repository_id: Optional[str] = None,
        collection_id: Optional[str] = None,
    ) -> None:
        """Emit CloudWatch metric.

        Args:
            metric_name: Name of the metric
            value: Metric value
            repository_id: Optional repository ID for dimensions
            collection_id: Optional collection ID for dimensions
        """
        try:
            dimensions = []
            if repository_id:
                dimensions.append({"Name": "RepositoryId", "Value": repository_id})
            if collection_id:
                dimensions.append({"Name": "CollectionId", "Value": collection_id})

            metric_data = {
                "MetricName": metric_name,
                "Value": value,
                "Unit": "Count",
            }

            if dimensions:
                metric_data["Dimensions"] = dimensions

            self.cloudwatch_client.put_metric_data(Namespace="LISA/BedrockKB", MetricData=[metric_data])
        except Exception as e:
            logger.warning(f"Failed to emit CloudWatch metric {metric_name}: {e}")

    def generate_metadata_json(
        self,
        repository: Dict[str, Any],
        collection: Optional[RagCollectionConfig],
        document_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate metadata.json content for Bedrock KB.

        Merges metadata from three sources with precedence:
        1. Repository metadata (lowest)
        2. Collection metadata (medium)
        3. Document metadata (highest)

        Args:
            repository: Repository configuration dictionary
            collection: Collection configuration (optional)
            document_metadata: Document-specific metadata (optional)

        Returns:
            Dictionary with metadataAttributes structure for Bedrock KB

        Raises:
            ValidationError: If metadata validation fails
        """
        # Start with empty metadata
        merged_metadata: Dict[str, Any] = {}

        # Merge repository metadata
        repo_metadata = repository.get("metadata")
        if repo_metadata:
            if isinstance(repo_metadata, dict):
                merged_metadata.update(repo_metadata.get("customFields", {}))
                # Add tags as individual fields
                for tag in repo_metadata.get("tags", []):
                    merged_metadata[f"tag_{tag}"] = True
            elif hasattr(repo_metadata, "customFields"):
                merged_metadata.update(repo_metadata.customFields)
                for tag in repo_metadata.tags:
                    merged_metadata[f"tag_{tag}"] = True

        # Merge collection metadata
        if collection and collection.metadata:
            coll_metadata = collection.metadata
            if isinstance(coll_metadata, CollectionMetadata):
                merged_metadata.update(coll_metadata.customFields)
                # Add tags as individual fields
                for tag in coll_metadata.tags:
                    merged_metadata[f"tag_{tag}"] = True
            elif isinstance(coll_metadata, dict):
                merged_metadata.update(coll_metadata.get("customFields", {}))
                for tag in coll_metadata.get("tags", []):
                    merged_metadata[f"tag_{tag}"] = True

        # Add collection identifiers
        if collection:
            merged_metadata["collectionId"] = collection.collectionId
            merged_metadata["collectionName"] = collection.name or collection.collectionId

        # Add repository identifier
        merged_metadata["repositoryId"] = repository.get("repositoryId", "")

        # Merge document-specific metadata (highest precedence)
        if document_metadata:
            merged_metadata.update(document_metadata)

        # Validate merged metadata
        self.validate_metadata(merged_metadata)

        # Return in Bedrock KB format
        return {"metadataAttributes": merged_metadata}

    def validate_metadata(
        self,
        metadata: Dict[str, Any],
        repository_id: Optional[str] = None,
        collection_id: Optional[str] = None,
    ) -> bool:
        """Validate metadata against Bedrock KB requirements.

        Args:
            metadata: Metadata dictionary to validate
            repository_id: Optional repository ID for metrics
            collection_id: Optional collection ID for metrics

        Returns:
            True if valid

        Raises:
            ValidationError: If validation fails
        """
        try:
            # Check total size
            metadata_json = json.dumps(metadata)
            metadata_size = len(metadata_json.encode("utf-8"))
            if metadata_size > MAX_METADATA_SIZE_BYTES:
                self._emit_metric("MetadataValidationFailed", 1.0, repository_id, collection_id)
                raise ValidationError(
                    f"Metadata size ({metadata_size} bytes) exceeds limit ({MAX_METADATA_SIZE_BYTES} bytes)"
                )

            # Validate each key-value pair
            for key, value in metadata.items():
                # Validate key
                self._validate_metadata_key(key)

                # Validate value type and size
                self._validate_metadata_value(key, value)

            return True
        except ValidationError:
            self._emit_metric("MetadataValidationFailed", 1.0, repository_id, collection_id)
            raise

    def _validate_metadata_key(self, key: str) -> None:
        """Validate metadata key.

        Args:
            key: Metadata key to validate

        Raises:
            ValidationError: If key is invalid
        """
        # Check for reserved fields
        if key in RESERVED_FIELDS:
            raise ValidationError(f"Metadata key '{key}' is reserved by Bedrock KB")

        # Check length
        if len(key) > MAX_METADATA_KEY_LENGTH:
            raise ValidationError(f"Metadata key '{key}' exceeds maximum length of {MAX_METADATA_KEY_LENGTH}")

        # Check format (alphanumeric, underscore, hyphen only)
        if not re.match(r"^[a-zA-Z0-9_-]+$", key):
            raise ValidationError(
                f"Metadata key '{key}' contains invalid characters. "
                "Only alphanumeric, underscore, and hyphen are allowed"
            )

    def _validate_metadata_value(self, key: str, value: Any) -> None:
        """Validate metadata value.

        Args:
            key: Metadata key (for error messages)
            value: Metadata value to validate

        Raises:
            ValidationError: If value is invalid
        """
        # Check type
        if not isinstance(value, (str, int, float, bool, list)):
            raise ValidationError(
                f"Metadata value for key '{key}' has invalid type '{type(value).__name__}'. "
                "Only string, number, boolean, and array are allowed"
            )

        # Check string length
        if isinstance(value, str) and len(value) > MAX_METADATA_VALUE_LENGTH:
            raise ValidationError(
                f"Metadata value for key '{key}' exceeds maximum length of {MAX_METADATA_VALUE_LENGTH}"
            )

        # Check array elements
        if isinstance(value, list):
            for item in value:
                if not isinstance(item, (str, int, float, bool)):
                    raise ValidationError(
                        f"Metadata array for key '{key}' contains invalid type '{type(item).__name__}'. "
                        "Array elements must be string, number, or boolean"
                    )
                if isinstance(item, str) and len(item) > MAX_METADATA_VALUE_LENGTH:
                    raise ValidationError(
                        f"Metadata array element for key '{key}' exceeds maximum length of {MAX_METADATA_VALUE_LENGTH}"
                    )

    def get_metadata_s3_key(self, document_s3_key: str) -> str:
        """Generate S3 key for metadata file.

        Args:
            document_s3_key: S3 key of the document

        Returns:
            S3 key for the metadata file (document_key + ".metadata.json")
        """
        return f"{document_s3_key}.metadata.json"

    def get_collection_metadata_cached(
        self, collection_id: str, repository_id: str, collection_repo
    ) -> Optional[Dict[str, Any]]:
        """Get collection metadata with caching.

        Args:
            collection_id: Collection ID
            repository_id: Repository ID
            collection_repo: Collection repository instance

        Returns:
            Collection metadata dictionary or None
        """
        cache_key = f"{repository_id}#{collection_id}"
        cached = self._collection_cache.get(cache_key)

        # Check cache
        if cached and time.time() - cached["timestamp"] < self._cache_ttl:
            logger.debug(f"Using cached metadata for collection {collection_id}")
            return cached["metadata"]

        # Fetch from DynamoDB
        try:
            collection = collection_repo.find_by_id(collection_id, repository_id)
            if collection and collection.metadata:
                metadata = collection.metadata
                if isinstance(metadata, CollectionMetadata):
                    # Flatten metadata for Bedrock KB compatibility
                    metadata_dict = {}
                    # Add tags as an array field
                    if metadata.tags:
                        metadata_dict["tags"] = metadata.tags
                    # Flatten customFields into top-level fields
                    metadata_dict.update(metadata.customFields)
                else:
                    metadata_dict = metadata

                # Cache result
                self._collection_cache[cache_key] = {"metadata": metadata_dict, "timestamp": time.time()}

                logger.debug(f"Cached metadata for collection {collection_id}")
                return metadata_dict
        except Exception as e:
            logger.warning(f"Failed to fetch collection metadata: {e}")

        return None

    def clear_cache(self, collection_id: Optional[str] = None, repository_id: Optional[str] = None) -> None:
        """Clear metadata cache.

        Args:
            collection_id: Specific collection to clear (optional)
            repository_id: Specific repository to clear (optional)
        """
        if collection_id and repository_id:
            cache_key = f"{repository_id}#{collection_id}"
            self._collection_cache.pop(cache_key, None)
            logger.debug(f"Cleared cache for collection {collection_id}")
        else:
            self._collection_cache.clear()
            logger.debug("Cleared all metadata cache")
