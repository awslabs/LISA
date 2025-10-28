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
from typing import Dict, List, Optional, Tuple

from models.domain_objects import RagCollectionConfig
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
        """Get a collection with access control."""
        collection = self.collection_repo.find_by_id(collection_id, repository_id)
        if not collection:
            raise ValidationError(f"Collection {collection_id} not found")
        if not self.has_access(collection, username, user_groups, is_admin):
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
        return self.collection_repo.count_by_repository(repository_id)

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
        return repository.get("embeddingModelId")
