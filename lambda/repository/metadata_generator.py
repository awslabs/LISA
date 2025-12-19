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
from typing import Any, Dict, Optional

from models.domain_objects import RagCollectionConfig
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
    """Static utility class for metadata generation and merging."""

    @staticmethod
    def _extract_tags_from_metadata(metadata: Any) -> set:
        """Extract tags from metadata object or dictionary.

        Args:
            metadata: Metadata object (dict or object with tags attribute)

        Returns:
            Set of tag strings
        """
        if isinstance(metadata, dict):
            return set(metadata.get("tags", []))
        elif hasattr(metadata, "tags") and metadata.tags:
            return set(metadata.tags)
        return set()

    @staticmethod
    def merge_metadata(
        repository: Dict[str, Any],
        collection: Optional[Dict[str, Any]],
        document_metadata: Optional[Dict[str, Any]] = None,
        for_bedrock_kb: bool = False,
    ) -> Dict[str, Any]:
        """
        Merge metadata from repository, collection, and document sources.

        This is the core metadata merging logic used by both ingestion jobs and Bedrock KB.
        Follows the hierarchy: repository → collection → document (document has highest precedence).

        Args:
            repository: Repository configuration dictionary
            collection: Collection configuration dictionary (optional)
            document_metadata: Document-specific metadata (optional)
            for_bedrock_kb: If True, formats tags for Bedrock KB (individual tag_ fields + comma-separated tags)
                           If False, keeps tags as array for ingestion jobs

        Returns:
            Merged metadata dictionary
        """
        merged_metadata: Dict[str, Any] = {}
        all_tags: set = set()

        # Helper function to merge non-tag metadata
        def merge_non_tag_metadata(metadata_source: Dict[str, Any]) -> None:
            for key, value in metadata_source.items():
                if key != "tags" and not isinstance(value, dict):
                    merged_metadata[key] = value

        # 1. Merge repository metadata (lowest precedence)
        repo_metadata = repository.get("metadata")
        if repo_metadata:
            all_tags.update(MetadataGenerator._extract_tags_from_metadata(repo_metadata))
            if isinstance(repo_metadata, dict):
                merge_non_tag_metadata(repo_metadata)

        # 2. Merge collection metadata (medium precedence)
        if collection and collection.get("metadata"):
            coll_metadata = collection["metadata"]
            all_tags.update(MetadataGenerator._extract_tags_from_metadata(coll_metadata))
            if isinstance(coll_metadata, dict):
                merge_non_tag_metadata(coll_metadata)

        # 3. Merge document-specific metadata (highest precedence)
        if document_metadata:
            all_tags.update(MetadataGenerator._extract_tags_from_metadata(document_metadata))
            merge_non_tag_metadata(document_metadata)

        # Add repository identifier
        merged_metadata["repositoryId"] = repository.get("repositoryId", "")
        merged_metadata["collectionId"] = collection.get("collectionId", "") if collection else "default"

        # Apply tag formatting based on target system
        if all_tags:
            if for_bedrock_kb:
                # Add tags as individual tag_ fields for Bedrock KB
                for tag in all_tags:
                    merged_metadata[f"tag_{tag}"] = True
                # Create comma-separated tags field
                merged_metadata["tags"] = ",".join(sorted(all_tags))
            else:
                # Keep tags as array for ingestion jobs
                merged_metadata["tags"] = list(all_tags)

        return merged_metadata

    @staticmethod
    def generate_metadata_json(
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
        # Convert collection to dict format for the shared merge function
        collection_dict = None
        if collection:
            collection_dict = collection.model_dump() if hasattr(collection, "model_dump") else collection.__dict__

        # Use shared merge function with Bedrock KB formatting
        merged_metadata = MetadataGenerator.merge_metadata(
            repository=repository,
            collection=collection_dict,
            document_metadata=document_metadata,
            for_bedrock_kb=True,
        )

        # For Bedrock KB: Remove empty collection fields if no collection provided
        if not collection:
            merged_metadata.pop("collectionId", None)
            merged_metadata.pop("collectionName", None)

        # Validate merged metadata
        MetadataGenerator.validate_metadata(merged_metadata)

        # Return in Bedrock KB format
        return {"metadataAttributes": merged_metadata}

    @staticmethod
    def validate_metadata(metadata: Dict[str, Any]) -> bool:
        """Validate metadata against Bedrock KB requirements.

        Args:
            metadata: Metadata dictionary to validate

        Returns:
            True if valid

        Raises:
            ValidationError: If validation fails
        """
        # Check total size
        metadata_json = json.dumps(metadata)
        metadata_size = len(metadata_json.encode("utf-8"))
        if metadata_size > MAX_METADATA_SIZE_BYTES:
            raise ValidationError(
                f"Metadata size ({metadata_size} bytes) exceeds limit ({MAX_METADATA_SIZE_BYTES} bytes)"
            )

        # Validate each key-value pair
        for key, value in metadata.items():
            # Validate key
            MetadataGenerator._validate_metadata_key(key)

            # Validate value type and size
            MetadataGenerator._validate_metadata_value(key, value)

        return True

    @staticmethod
    def _validate_metadata_key(key: str) -> None:
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

    @staticmethod
    def _validate_metadata_value(key: str, value: Any) -> None:
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
