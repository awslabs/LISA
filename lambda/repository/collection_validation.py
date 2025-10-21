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

"""Validation service for collection configurations."""

import logging
import re
from typing import Any, Dict, List, Optional

from models.domain_objects import (
    ChunkingStrategy,
    CollectionMetadata,
    CreateCollectionRequest,
    FixedChunkingStrategy,
    FixedSizeChunkingStrategy,
    UpdateCollectionRequest,
)
from repository.collection_repo import CollectionRepository
from repository.vector_store_repo import VectorStoreRepository
from utilities.validation import ValidationError

logger = logging.getLogger(__name__)

# Validation constants
MAX_NAME_LENGTH = 100
MAX_TAG_LENGTH = 50
MAX_TAGS_COUNT = 50
MIN_CHUNK_SIZE = 100
MAX_CHUNK_SIZE = 10000
NAME_PATTERN = re.compile(r"^[a-zA-Z0-9 _-]+$")
TAG_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class CollectionValidationService:
    """Service for validating collection configurations."""

    def __init__(
        self,
        collection_repo: Optional[CollectionRepository] = None,
        vector_store_repo: Optional[VectorStoreRepository] = None,
    ):
        """
        Initialize the validation service.

        Args:
            collection_repo: Collection repository for database checks
            vector_store_repo: Vector store repository for parent validation
        """
        self.collection_repo = collection_repo or CollectionRepository()
        self.vector_store_repo = vector_store_repo or VectorStoreRepository()

    def validate_create_request(self, request: CreateCollectionRequest, repository_id: str) -> Dict[str, Any]:
        """
        Validate a collection creation request.

        Args:
            request: The creation request to validate
            repository_id: The parent repository ID

        Returns:
            Dictionary of validation results with any warnings

        Raises:
            ValidationError: If validation fails
        """
        errors = []
        warnings = []

        # Validate name
        try:
            self._validate_name(request.name)
        except ValidationError as e:
            errors.append(str(e))

        # Check name uniqueness
        try:
            self._validate_name_uniqueness(repository_id, request.name)
        except ValidationError as e:
            errors.append(str(e))

        # Validate allowed groups against parent
        if request.allowedGroups is not None:
            try:
                parent_config = self.vector_store_repo.find_repository_by_id(repository_id)
                self._validate_allowed_groups(request.allowedGroups, parent_config.get("allowedGroups", []))
            except ValidationError as e:
                errors.append(str(e))
            except ValueError as e:
                errors.append(f"Failed to retrieve parent repository: {str(e)}")

        # Validate chunking strategy
        if request.chunkingStrategy:
            try:
                self._validate_chunking_strategy(request.chunkingStrategy)
            except ValidationError as e:
                errors.append(str(e))

        # Validate metadata
        if request.metadata:
            try:
                self._validate_metadata(request.metadata)
            except ValidationError as e:
                errors.append(str(e))

        # Validate embedding model if provided
        if request.embeddingModel:
            try:
                self._validate_embedding_model(request.embeddingModel)
            except ValidationError as e:
                errors.append(str(e))

        if errors:
            error_message = "Validation failed: " + "; ".join(errors)
            logger.warning(f"Collection creation validation failed: {error_message}")
            raise ValidationError(error_message)

        return {"valid": True, "warnings": warnings}

    def validate_update_request(
        self,
        request: UpdateCollectionRequest,
        collection_id: str,
        repository_id: str,
        has_documents: bool = False,
    ) -> Dict[str, Any]:
        """
        Validate a collection update request.

        Args:
            request: The update request to validate
            collection_id: The collection ID being updated
            repository_id: The parent repository ID
            has_documents: Whether the collection has existing documents

        Returns:
            Dictionary of validation results with any warnings

        Raises:
            ValidationError: If validation fails
        """
        errors = []
        warnings = []

        # Validate name if provided
        if request.name is not None:
            try:
                self._validate_name(request.name)
                # Check uniqueness (excluding current collection)
                existing = self.collection_repo.find_by_name(repository_id, request.name)
                if existing and existing.collectionId != collection_id:
                    errors.append(f"Collection name '{request.name}' already exists in this repository")
            except ValidationError as e:
                errors.append(str(e))

        # Validate allowed groups if provided
        if request.allowedGroups is not None:
            try:
                parent_config = self.vector_store_repo.find_repository_by_id(repository_id)
                self._validate_allowed_groups(request.allowedGroups, parent_config.get("allowedGroups", []))
            except ValidationError as e:
                errors.append(str(e))
            except ValueError as e:
                errors.append(f"Failed to retrieve parent repository: {str(e)}")

        # Validate chunking strategy if provided
        if request.chunkingStrategy:
            try:
                self._validate_chunking_strategy(request.chunkingStrategy)
                # Warn if changing strategy with existing documents
                if has_documents:
                    warnings.append(
                        "Changing chunking strategy will only affect new documents. "
                        "Existing documents will retain their original chunking. "
                        "Consider re-ingesting existing documents if needed."
                    )
            except ValidationError as e:
                errors.append(str(e))

        # Validate metadata if provided
        if request.metadata:
            try:
                self._validate_metadata(request.metadata)
            except ValidationError as e:
                errors.append(str(e))

        if errors:
            error_message = "Validation failed: " + "; ".join(errors)
            logger.warning(f"Collection update validation failed: {error_message}")
            raise ValidationError(error_message)

        return {"valid": True, "warnings": warnings}

    def _validate_name(self, name: str) -> None:
        """
        Validate collection name.

        Args:
            name: The collection name to validate

        Raises:
            ValidationError: If name is invalid
        """
        if not name or not name.strip():
            raise ValidationError("Collection name cannot be empty")

        if len(name) > MAX_NAME_LENGTH:
            raise ValidationError(f"Collection name must be {MAX_NAME_LENGTH} characters or less")

        if not NAME_PATTERN.match(name):
            raise ValidationError(
                "Collection name must contain only alphanumeric characters, spaces, hyphens, and underscores"
            )

    def _validate_name_uniqueness(self, repository_id: str, name: str) -> None:
        """
        Validate that collection name is unique within repository.

        Args:
            repository_id: The repository ID
            name: The collection name

        Raises:
            ValidationError: If name already exists
        """
        existing = self.collection_repo.find_by_name(repository_id, name)
        if existing:
            raise ValidationError(f"Collection name '{name}' already exists in this repository")

    def _validate_allowed_groups(self, collection_groups: List[str], parent_groups: List[str]) -> None:
        """
        Validate that collection groups are a subset of parent groups.

        Args:
            collection_groups: The collection's allowed groups
            parent_groups: The parent repository's allowed groups

        Raises:
            ValidationError: If groups are not a valid subset
        """
        if not collection_groups:
            return  # Empty list is valid (inherits from parent)

        if not parent_groups:
            # Parent has no restrictions, collection can have any groups
            return

        # Check if collection groups are a subset of parent groups
        invalid_groups = set(collection_groups) - set(parent_groups)
        if invalid_groups:
            raise ValidationError(
                f"Collection allowedGroups must be a subset of parent repository groups. "
                f"Invalid groups: {', '.join(sorted(invalid_groups))}"
            )

    def _validate_chunking_strategy(self, strategy: ChunkingStrategy) -> None:
        """
        Validate chunking strategy parameters.

        Args:
            strategy: The chunking strategy to validate

        Raises:
            ValidationError: If strategy is invalid
        """
        # Handle both legacy (FixedChunkingStrategy) and new (FixedSizeChunkingStrategy) formats
        if isinstance(strategy, FixedSizeChunkingStrategy):
            # Validate chunk size
            if strategy.chunkSize < MIN_CHUNK_SIZE or strategy.chunkSize > MAX_CHUNK_SIZE:
                raise ValidationError(f"chunkSize must be between {MIN_CHUNK_SIZE} and {MAX_CHUNK_SIZE}")

            # Validate chunk overlap
            if strategy.chunkOverlap < 0:
                raise ValidationError("chunkOverlap must be non-negative")

            if strategy.chunkOverlap > strategy.chunkSize / 2:
                raise ValidationError(
                    f"chunkOverlap ({strategy.chunkOverlap}) must be less than or equal to "
                    f"half of chunkSize ({strategy.chunkSize / 2})"
                )

        elif isinstance(strategy, FixedChunkingStrategy):
            # Legacy format validation
            if strategy.size < MIN_CHUNK_SIZE or strategy.size > MAX_CHUNK_SIZE:
                raise ValidationError(f"chunk size must be between {MIN_CHUNK_SIZE} and {MAX_CHUNK_SIZE}")

            if strategy.overlap < 0:
                raise ValidationError("chunk overlap must be non-negative")

            if strategy.overlap > strategy.size / 2:
                raise ValidationError(
                    f"chunk overlap ({strategy.overlap}) must be less than or equal to "
                    f"half of chunk size ({strategy.size / 2})"
                )

        else:
            # Unsupported strategy type
            raise ValidationError(
                f"Unsupported chunking strategy type: {strategy.type}. "
                f"Only FIXED and FIXED_SIZE strategies are currently supported."
            )

    def _validate_metadata(self, metadata: CollectionMetadata) -> None:
        """
        Validate collection metadata.

        Args:
            metadata: The metadata to validate

        Raises:
            ValidationError: If metadata is invalid
        """
        # Validate tags
        if len(metadata.tags) > MAX_TAGS_COUNT:
            raise ValidationError(f"Maximum {MAX_TAGS_COUNT} tags allowed per collection")

        for tag in metadata.tags:
            if len(tag) > MAX_TAG_LENGTH:
                raise ValidationError(f"Each tag must be {MAX_TAG_LENGTH} characters or less")

            if not TAG_PATTERN.match(tag):
                raise ValidationError(
                    f"Tag '{tag}' contains invalid characters. "
                    "Tags must contain only alphanumeric characters, hyphens, and underscores"
                )

    def _validate_embedding_model(self, embedding_model: str) -> None:
        """
        Validate embedding model ID.

        Args:
            embedding_model: The embedding model ID to validate

        Raises:
            ValidationError: If embedding model is invalid
        """
        if not embedding_model or not embedding_model.strip():
            raise ValidationError("Embedding model ID cannot be empty")

        # Note: Additional validation could check if the model exists in the system
        # This would require integration with the model management service
        # For now, we just validate it's a non-empty string

    def validate_merged_metadata(
        self, parent_metadata: Optional[CollectionMetadata], collection_metadata: Optional[CollectionMetadata]
    ) -> None:
        """
        Validate that merged metadata doesn't exceed limits.

        Args:
            parent_metadata: Parent repository metadata
            collection_metadata: Collection-specific metadata

        Raises:
            ValidationError: If merged metadata exceeds limits
        """
        if not parent_metadata and not collection_metadata:
            return

        # Merge metadata
        merged = CollectionMetadata.merge(parent_metadata, collection_metadata)

        # Validate merged result
        if len(merged.tags) > MAX_TAGS_COUNT:
            raise ValidationError(
                f"Merged metadata has {len(merged.tags)} tags, maximum is {MAX_TAGS_COUNT}. "
                f"Reduce collection-specific tags to stay within limit."
            )


def validate_collection_name(name: str) -> bool:
    """
    Quick validation function for collection name.

    Args:
        name: The collection name to validate

    Returns:
        True if valid

    Raises:
        ValidationError: If name is invalid
    """
    if not name or not name.strip():
        raise ValidationError("Collection name cannot be empty")

    if len(name) > MAX_NAME_LENGTH:
        raise ValidationError(f"Collection name must be {MAX_NAME_LENGTH} characters or less")

    if not NAME_PATTERN.match(name):
        raise ValidationError(
            "Collection name must contain only alphanumeric characters, spaces, hyphens, and underscores"
        )

    return True


def validate_groups_subset(collection_groups: List[str], parent_groups: List[str]) -> bool:
    """
    Quick validation that collection groups are subset of parent groups.

    Args:
        collection_groups: Collection's allowed groups
        parent_groups: Parent repository's allowed groups

    Returns:
        True if valid

    Raises:
        ValidationError: If not a valid subset
    """
    if not collection_groups or not parent_groups:
        return True

    invalid_groups = set(collection_groups) - set(parent_groups)
    if invalid_groups:
        raise ValidationError(
            f"Collection allowedGroups must be a subset of parent repository groups. "
            f"Invalid groups: {', '.join(sorted(invalid_groups))}"
        )

    return True
