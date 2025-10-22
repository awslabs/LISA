#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Collection service for business logic."""

from typing import List, Optional, Dict, Tuple
from models.domain_objects import RagCollectionConfig
from repository.collection_repo import CollectionRepository
from repository.collection_access_control_helpers import can_access_collection, validate_collection_access, can_modify_collection
from utilities.validation import ValidationError


class CollectionService:
    """Service for collection operations."""

    def __init__(self, collection_repo: Optional[CollectionRepository] = None):
        self.collection_repo = collection_repo or CollectionRepository()

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
        validate_collection_access(collection, username, user_groups, is_admin)
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
        filtered = [c for c in collections if can_access_collection(c, username, user_groups, is_admin)]
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
        if not can_modify_collection(collection, username, is_admin):
            raise ValidationError(f"Permission denied to delete collection {collection_id}")
        self.collection_repo.delete(collection_id, repository_id)
