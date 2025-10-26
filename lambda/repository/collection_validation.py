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
from typing import Any, Dict, List, Optional

from models.domain_objects import CollectionMetadata, CreateCollectionRequest, UpdateCollectionRequest
from repository.collection_repo import CollectionRepository
from repository.vector_store_repo import VectorStoreRepository
from utilities.validation import ValidationError

logger = logging.getLogger(__name__)


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

        # Check name uniqueness if provided
        if request.name is not None:
            existing = self.collection_repo.find_by_name(repository_id, request.name)
            if existing and existing.collectionId != collection_id:
                errors.append(f"Collection name '{request.name}' already exists in this repository")

        # Validate allowed groups if provided
        if request.allowedGroups is not None:
            try:
                parent_config = self.vector_store_repo.find_repository_by_id(repository_id)
                self._validate_allowed_groups(request.allowedGroups, parent_config.get("allowedGroups", []))
            except ValidationError as e:
                errors.append(str(e))
            except ValueError as e:
                errors.append(f"Failed to retrieve parent repository: {str(e)}")

        # Warn if changing strategy with existing documents
        if request.chunkingStrategy and has_documents:
            warnings.append(
                "Changing chunking strategy will only affect new documents. "
                "Existing documents will retain their original chunking. "
                "Consider re-ingesting existing documents if needed."
            )

        if errors:
            error_message = "Validation failed: " + "; ".join(errors)
            logger.warning(f"Collection update validation failed: {error_message}")
            raise ValidationError(error_message)

        return {"valid": True, "warnings": warnings}

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

        # Validate merged result (Pydantic will validate on creation)
        if len(merged.tags) > 50:
            raise ValidationError(
                f"Merged metadata has {len(merged.tags)} tags, maximum is 50. "
                f"Reduce collection-specific tags to stay within limit."
            )


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
