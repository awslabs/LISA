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


"""Collection service for business logic."""

import logging
from typing import Any, Dict, List, Optional, Tuple

from models.domain_objects import CollectionMetadata, RagCollectionConfig
from repository.collection_repo import CollectionRepository
from repository.vector_store_repo import VectorStoreRepository
from utilities.validation import ValidationError

logger = logging.getLogger(__name__)


class CollectionService:
    """Service for collection operations."""

    def __init__(
        self,
        collection_repo: Optional[CollectionRepository] = None,
        vector_store_repo: Optional[VectorStoreRepository] = None,
    ):
        self.collection_repo = collection_repo or CollectionRepository()
        self.vector_store_repo = vector_store_repo or VectorStoreRepository()

    def has_access(
        self,
        collection: RagCollectionConfig,
        username: str,
        user_groups: List[str],
        is_admin: bool,
        require_write: bool = False,
    ) -> bool:
        """Check if user has access to a collection."""
        if is_admin:
            return True
        if collection.createdBy == username:
            return True
        if require_write:
            return False
        if not collection.private and bool(set(user_groups) & set(collection.allowedGroups or [])):
            return True
        return False

    def create_collection(
        self,
        collection: RagCollectionConfig,
        username: str,
        is_admin: bool,
    ) -> RagCollectionConfig:
        """Create a new collection."""
        return self.collection_repo.create(collection)

    def get_collection(
        self,
        repository_id: str,
        collection_id: str,
        username: str,
        user_groups: List[str],
        is_admin: bool,
    ) -> RagCollectionConfig:
        """Get a collection with access control.

        Args:
            repository_id: Repository ID
            collection_id: Collection ID
            username: Username for access control (deprecated, use username)
            user_groups: User groups for access control
            is_admin: Whether user is admin
            username: Username for access control (preferred over username)
        """
        # Support both username and username parameters for backwards compatibility
        effective_username = username or username
        collection = self.collection_repo.find_by_id(collection_id, repository_id)
        if not collection:
            raise ValidationError(f"Collection {collection_id} not found")
        if not self.has_access(collection, effective_username, user_groups, is_admin):
            raise ValidationError(f"Permission denied for collection {collection_id}")
        return collection

    def list_collections(
        self,
        repository_id: str,
        username: str,
        user_groups: List[str],
        is_admin: bool,
        page_size: int = 20,
        last_evaluated_key: Optional[Dict[str, str]] = None,
    ) -> Tuple[List[RagCollectionConfig], Optional[Dict[str, str]]]:
        """List collections with access control."""
        collections, key = self.collection_repo.list_by_repository(
            repository_id, page_size=page_size, last_evaluated_key=last_evaluated_key
        )
        filtered = [c for c in collections if self.has_access(c, username, user_groups, is_admin)]
        return filtered, key

    def update_collection(
        self,
        collection_id: str,
        repository_id: str,
        request: Any,
        username: str,
        user_groups: List[str],
        is_admin: bool,
    ) -> RagCollectionConfig:
        """Update a collection with access control.

        Args:
            collection_id: Collection ID to update
            repository_id: Repository ID
            request: UpdateCollectionRequest with fields to update
            username: Username for access control
            user_groups: User groups for access control
            is_admin: Whether user is admin

        Returns:
            Updated collection
        """
        collection = self.collection_repo.find_by_id(collection_id, repository_id)
        if not collection:
            raise ValidationError(f"Collection {collection_id} not found")
        if not self.has_access(collection, username, user_groups, is_admin, require_write=True):
            raise ValidationError(f"Permission denied to update collection {collection_id}")

        updates = {}

        # Build updates from request
        if hasattr(request, "description") and request.description is not None:
            updates["description"] = request.description
        if hasattr(request, "embeddingModel") and request.embeddingModel is not None:
            updates["embeddingModel"] = request.embeddingModel
        if hasattr(request, "chunkingStrategy") and request.chunkingStrategy is not None:
            updates["chunkingStrategy"] = request.chunkingStrategy
        if hasattr(request, "allowedGroups") and request.allowedGroups is not None:
            updates["allowedGroups"] = request.allowedGroups
        if hasattr(request, "metadata") and request.metadata is not None:
            updates["metadata"] = request.metadata
        if hasattr(request, "private") and request.private is not None:
            updates["private"] = request.private
        if hasattr(request, "allowChunkingOverride") and request.allowChunkingOverride is not None:
            updates["allowChunkingOverride"] = request.allowChunkingOverride
        if hasattr(request, "pipelines") and request.pipelines is not None:
            updates["pipelines"] = request.pipelines

        # Update collection
        updated = self.collection_repo.update(collection_id, repository_id, updates)
        return updated

    def delete_collection(
        self,
        repository_id: str,
        collection_id: str,
        username: str,
        user_groups: List[str],
        is_admin: bool,
    ) -> None:
        """Delete a collection with access control."""
        collection = self.collection_repo.find_by_id(collection_id, repository_id)
        if not collection:
            raise ValidationError(f"Collection {collection_id} not found")
        if not self.has_access(collection, username, user_groups, is_admin, require_write=True):
            raise ValidationError(f"Permission denied to delete collection {collection_id}")
        self.collection_repo.delete(collection_id, repository_id)

    def get_collection_by_name(
        self,
        repository_id: str,
        collection_name: str,
        username: str,
        user_groups: List[str],
        is_admin: bool,
    ) -> RagCollectionConfig:
        """Get a collection by name with access control."""
        collection = self.collection_repo.find_by_name(repository_id, collection_name)
        if not collection:
            raise ValidationError(f"Collection '{collection_name}' not found")
        if not self.has_access(collection, username, user_groups, is_admin):
            raise ValidationError(f"Permission denied for collection '{collection_name}'")
        return collection

    def count_collections(self, repository_id: str) -> int:
        """Count total collections in a repository.

        Args:
            repository_id: Repository ID

        Returns:
            Total count of collections
        """
        count = self.collection_repo.count_by_repository(repository_id)
        return int(count) if count is not None else 0

    def get_collection_model(
        self,
        repository_id: str,
        collection_id: str,
        username: str,
        user_groups: List[str],
        is_admin: bool,
    ) -> Optional[str]:
        """Get embedding model from collection or repository default.

        Args:
            repository_id: Repository ID
            collection_id: Collection ID
            username: Username for access control
            user_groups: User groups for access control
            is_admin: Whether user is admin

        Returns:
            Embedding model name from collection or repository default
        """
        try:
            collection = self.collection_repo.find_by_id(collection_id, repository_id)
            if collection.embeddingModel:
                return collection.embeddingModel
        except ValidationError as e:
            logger.warning(f"Failed to get collection '{collection_id}': {e}, using repository default")

        repository = self.vector_store_repo.find_repository_by_id(repository_id)
        embedding_model_id = repository.get("embeddingModelId")
        return str(embedding_model_id) if embedding_model_id is not None else None

    def get_collection_metadata(
        self,
        repository: VectorStoreRepository,
        collection: RagCollectionConfig,
        metadata: Optional[CollectionMetadata] = None,
    ) -> Dict[str, Any]:
        """Get collection metadata with merges from repository."""
        merged_metadata: Dict[str, Any] = {}

        # Repository metadata
        repo_metadata = repository.get("metadata") if isinstance(repository, dict) else None
        if repo_metadata:
            if isinstance(repo_metadata, CollectionMetadata):
                merged_metadata.update(repo_metadata.customFields)
            elif isinstance(repo_metadata, dict):
                merged_metadata.update(repo_metadata)

        # Collection metadata
        if collection:
            coll_metadata = collection.get("metadata") if isinstance(collection, dict) else collection.metadata
            if coll_metadata:
                if isinstance(coll_metadata, CollectionMetadata):
                    merged_metadata.update(coll_metadata.customFields)
                elif isinstance(coll_metadata, dict):
                    merged_metadata.update(coll_metadata)

        # Passed metadata
        if metadata:
            if isinstance(metadata, CollectionMetadata):
                merged_metadata.update(metadata.customFields)
            elif isinstance(metadata, dict):
                merged_metadata.update(metadata)

        return merged_metadata
