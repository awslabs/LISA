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

"""Collection management service with business logic."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from models.domain_objects import (
    CollectionMetadata,
    CollectionSortBy,
    CollectionStatus,
    CreateCollectionRequest,
    RagCollectionConfig,
    SortOrder,
    UpdateCollectionRequest,
)
from repository.collection_access_control import CollectionAccessControlService
from repository.collection_repo import CollectionRepository, CollectionRepositoryError
from repository.collection_validation import CollectionValidationService
from repository.rag_document_repo import RagDocumentRepository
from repository.vector_store_repo import VectorStoreRepository
from utilities.access_control import Permission
from utilities.validation import ValidationError

logger = logging.getLogger(__name__)


class CollectionManagementService:
    """Service for managing collection lifecycle and business logic."""

    def __init__(
        self,
        collection_repo: Optional[CollectionRepository] = None,
        vector_store_repo: Optional[VectorStoreRepository] = None,
        validation_service: Optional[CollectionValidationService] = None,
        access_control_service: Optional[CollectionAccessControlService] = None,
        document_repo: Optional[RagDocumentRepository] = None,
    ):
        """
        Initialize the collection management service.

        Args:
            collection_repo: Collection repository
            vector_store_repo: Vector store repository
            validation_service: Validation service
            access_control_service: Access control service
            document_repo: Document repository
        """
        self.collection_repo = collection_repo or CollectionRepository()
        self.document_repo = document_repo
        self.vector_store_repo = vector_store_repo or VectorStoreRepository()
        self.validation_service = validation_service or CollectionValidationService(
            self.collection_repo, self.vector_store_repo
        )
        self.access_control_service = access_control_service or CollectionAccessControlService(
            self.collection_repo, self.vector_store_repo
        )

    def create_collection(
        self,
        request: CreateCollectionRequest,
        repository_id: str,
        user_id: str,
        user_groups: List[str],
        is_admin: bool,
    ) -> RagCollectionConfig:
        """
        Create a new collection with inheritance and validation.

        Args:
            request: Creation request
            repository_id: Parent repository ID
            user_id: User creating the collection
            user_groups: User's group memberships
            is_admin: Whether user is admin

        Returns:
            Created collection configuration

        Raises:
            ValidationError: If validation fails
            CollectionRepositoryError: If creation fails
        """
        # Check permission to create collections in repository
        access_decision = self.access_control_service.check_repository_permission(
            user_id, user_groups, is_admin, repository_id, Permission.WRITE
        )
        if not access_decision.allowed:
            raise ValidationError(f"Permission denied: {access_decision.reason}")

        # Validate request
        self.validation_service.validate_create_request(request, repository_id)

        # Get parent repository configuration
        parent_config = self.vector_store_repo.find_repository_by_id(repository_id)

        # Apply inheritance rules
        collection_config = self._apply_inheritance(request, parent_config, repository_id, user_id)

        # Create collection
        created = self.collection_repo.create(collection_config)

        logger.info(f"Created collection {created.collectionId} in repository {repository_id}")
        return created

    def get_collection(
        self,
        collection_id: str,
        repository_id: str,
        user_id: str,
        user_groups: List[str],
        is_admin: bool,
    ) -> RagCollectionConfig:
        """
        Get a collection by ID with access control.

        Args:
            collection_id: Collection ID
            repository_id: Repository ID
            user_id: User requesting the collection
            user_groups: User's group memberships
            is_admin: Whether user is admin

        Returns:
            Collection configuration

        Raises:
            ValidationError: If access denied or not found
        """
        # Check permission
        access_decision = self.access_control_service.check_collection_permission(
            user_id, user_groups, is_admin, collection_id, repository_id, Permission.READ
        )
        if not access_decision.allowed:
            raise ValidationError(f"Permission denied: {access_decision.reason}")

        collection = self.collection_repo.find_by_id(collection_id, repository_id)
        if not collection:
            raise ValidationError(f"Collection '{collection_id}' not found")

        return collection

    def update_collection(
        self,
        collection_id: str,
        repository_id: str,
        request: UpdateCollectionRequest,
        user_id: str,
        user_groups: List[str],
        is_admin: bool,
    ) -> Tuple[RagCollectionConfig, List[str]]:
        """
        Update a collection with validation.

        Args:
            collection_id: Collection ID
            repository_id: Repository ID
            request: Update request
            user_id: User updating the collection
            user_groups: User's group memberships
            is_admin: Whether user is admin

        Returns:
            Tuple of (updated collection, list of warnings)

        Raises:
            ValidationError: If validation fails or access denied
            CollectionRepositoryError: If update fails
        """
        # Check permission
        access_decision = self.access_control_service.check_collection_permission(
            user_id, user_groups, is_admin, collection_id, repository_id, Permission.WRITE
        )
        if not access_decision.allowed:
            raise ValidationError(f"Permission denied: {access_decision.reason}")

        # Get existing collection
        existing = self.collection_repo.find_by_id(collection_id, repository_id)
        if not existing:
            raise ValidationError(f"Collection '{collection_id}' not found")

        # Check if collection has documents (for chunking strategy warning)
        has_documents = False
        if self.document_repo:
            try:
                doc_count = self.document_repo.count_documents(repository_id, collection_id)
                has_documents = doc_count > 0
            except Exception as e:
                logger.warning(f"Failed to check document count for collection {collection_id}: {e}")
                # Continue without document count check

        # Validate update request
        validation_result = self.validation_service.validate_update_request(
            request, collection_id, repository_id, has_documents
        )

        # Build updates dictionary
        updates = {}
        if request.name is not None:
            updates["name"] = request.name
        if request.description is not None:
            updates["description"] = request.description
        if request.chunkingStrategy is not None:
            updates["chunkingStrategy"] = request.chunkingStrategy
        if request.allowedGroups is not None:
            updates["allowedGroups"] = request.allowedGroups
        if request.metadata is not None:
            updates["metadata"] = request.metadata
        if request.private is not None:
            updates["private"] = request.private
        if request.allowChunkingOverride is not None:
            updates["allowChunkingOverride"] = request.allowChunkingOverride
        if request.pipelines is not None:
            updates["pipelines"] = request.pipelines
        if request.status is not None:
            updates["status"] = request.status

        # Update collection
        updated = self.collection_repo.update(
            collection_id, repository_id, updates, expected_version=existing.updatedAt.isoformat()
        )

        # Clear access control cache for this collection
        self.access_control_service.clear_cache_for_collection(collection_id)

        logger.info(f"Updated collection {collection_id}")
        return updated, validation_result.get("warnings", [])

    def delete_collection(
        self,
        collection_id: str,
        repository_id: str,
        user_id: str,
        user_groups: List[str],
        is_admin: bool,
        hard_delete: bool = False,
    ) -> bool:
        """
        Delete a collection (soft or hard delete).

        Args:
            collection_id: Collection ID
            repository_id: Repository ID
            user_id: User deleting the collection
            user_groups: User's group memberships
            is_admin: Whether user is admin
            hard_delete: Whether to hard delete (remove from DB) or soft delete (mark as deleted)

        Returns:
            True if deletion was successful

        Raises:
            ValidationError: If access denied or not found
            CollectionRepositoryError: If deletion fails
        """
        # Check permission (admin required for delete)
        access_decision = self.access_control_service.check_collection_permission(
            user_id, user_groups, is_admin, collection_id, repository_id, Permission.ADMIN
        )
        if not access_decision.allowed:
            raise ValidationError(f"Permission denied: {access_decision.reason}")

        # Get existing collection
        existing = self.collection_repo.find_by_id(collection_id, repository_id)
        if not existing:
            raise ValidationError(f"Collection '{collection_id}' not found")

        # Prevent deletion of default collection
        parent_config = self.vector_store_repo.find_repository_by_id(repository_id)
        default_collection_id = parent_config.get("embeddingModelId", "")
        if collection_id == default_collection_id:
            raise ValidationError("Cannot delete the default collection")

        # Delete associated documents if document_repo is available
        if self.document_repo:
            try:
                # Get all documents in the collection with pagination
                last_key = None
                total_deleted = 0
                batch_size = 100
                
                while True:
                    docs, last_key, _ = self.document_repo.list_all(
                        repository_id=repository_id,
                        collection_id=collection_id,
                        last_evaluated_key=last_key,
                        limit=batch_size,
                        join_docs=True  # Include subdoc IDs for vector store deletion
                    )
                    
                    if not docs:
                        break
                    
                    logger.info(f"Processing batch of {len(docs)} documents from collection {collection_id}")
                    
                    # Delete embeddings from vector store
                    try:
                        self._delete_embeddings_from_vector_store(docs, repository_id, collection_id)
                    except Exception as e:
                        logger.error(f"Failed to delete embeddings from vector store: {e}")
                        # Continue with other deletions
                    
                    # Delete documents from S3
                    self.document_repo.delete_s3_docs(repository_id, [doc.model_dump() for doc in docs])
                    
                    # Delete document records from DynamoDB
                    for doc in docs:
                        try:
                            self.document_repo.delete_by_id(doc.document_id)
                            total_deleted += 1
                        except Exception as e:
                            logger.warning(f"Failed to delete document {doc.document_id}: {e}")
                    
                    # Break if no more pages
                    if not last_key:
                        break
                
                if total_deleted > 0:
                    logger.info(f"Deleted {total_deleted} documents from collection {collection_id}")
                    
            except Exception as e:
                logger.error(f"Failed to delete documents for collection {collection_id}: {e}")
                # Continue with collection deletion even if document cleanup fails
                # The documents will be orphaned but the collection will be deleted

        if hard_delete:
            # Hard delete - remove from database
            self.collection_repo.delete(collection_id, repository_id)
            logger.info(f"Hard deleted collection {collection_id}")
        else:
            # Soft delete - mark as deleted
            updates = {"status": CollectionStatus.DELETED}
            self.collection_repo.update(collection_id, repository_id, updates)
            logger.info(f"Soft deleted collection {collection_id}")

        # Clear access control cache
        self.access_control_service.clear_cache_for_collection(collection_id)

        return True

    def list_collections(
        self,
        repository_id: str,
        user_id: str,
        user_groups: List[str],
        is_admin: bool,
        page_size: int = 20,
        last_evaluated_key: Optional[Dict[str, str]] = None,
        filter_text: Optional[str] = None,
        status_filter: Optional[CollectionStatus] = None,
        sort_by: CollectionSortBy = CollectionSortBy.CREATED_AT,
        sort_order: SortOrder = SortOrder.DESC,
    ) -> Tuple[List[RagCollectionConfig], Optional[Dict[str, str]]]:
        """
        List collections with filtering and pagination.

        Args:
            repository_id: Repository ID
            user_id: User requesting the list
            user_groups: User's group memberships
            is_admin: Whether user is admin
            page_size: Number of items per page
            last_evaluated_key: Pagination token
            filter_text: Text filter for name/description
            status_filter: Status filter
            sort_by: Sort field
            sort_order: Sort order

        Returns:
            Tuple of (list of collections, pagination token)

        Raises:
            ValidationError: If access denied
        """
        # Check permission to access repository
        access_decision = self.access_control_service.check_repository_permission(
            user_id, user_groups, is_admin, repository_id, Permission.READ
        )
        if not access_decision.allowed:
            raise ValidationError(f"Permission denied: {access_decision.reason}")

        # Get all collections in repository
        collections, next_key = self.collection_repo.list_by_repository(
            repository_id, page_size, last_evaluated_key, filter_text, status_filter, sort_by, sort_order
        )

        # Filter by user access (unless admin)
        if not is_admin:
            accessible_collections = []
            for collection in collections:
                # Check if user can access this collection
                if self._can_user_access_collection(user_id, user_groups, collection):
                    accessible_collections.append(collection)
            collections = accessible_collections

        return collections, next_key

    def archive_collection(
        self,
        collection_id: str,
        repository_id: str,
        user_id: str,
        user_groups: List[str],
        is_admin: bool,
    ) -> RagCollectionConfig:
        """
        Archive a collection.

        Args:
            collection_id: Collection ID
            repository_id: Repository ID
            user_id: User archiving the collection
            user_groups: User's group memberships
            is_admin: Whether user is admin

        Returns:
            Updated collection configuration

        Raises:
            ValidationError: If access denied or not found
        """
        # Check permission
        access_decision = self.access_control_service.check_collection_permission(
            user_id, user_groups, is_admin, collection_id, repository_id, Permission.ADMIN
        )
        if not access_decision.allowed:
            raise ValidationError(f"Permission denied: {access_decision.reason}")

        # Update status to archived
        updates = {"status": CollectionStatus.ARCHIVED}
        updated = self.collection_repo.update(collection_id, repository_id, updates)

        logger.info(f"Archived collection {collection_id}")
        return updated

    def restore_collection(
        self,
        collection_id: str,
        repository_id: str,
        user_id: str,
        user_groups: List[str],
        is_admin: bool,
    ) -> RagCollectionConfig:
        """
        Restore an archived collection.

        Args:
            collection_id: Collection ID
            repository_id: Repository ID
            user_id: User restoring the collection
            user_groups: User's group memberships
            is_admin: Whether user is admin

        Returns:
            Updated collection configuration

        Raises:
            ValidationError: If access denied or not found
        """
        # Check permission
        access_decision = self.access_control_service.check_collection_permission(
            user_id, user_groups, is_admin, collection_id, repository_id, Permission.ADMIN
        )
        if not access_decision.allowed:
            raise ValidationError(f"Permission denied: {access_decision.reason}")

        # Update status to active
        updates = {"status": CollectionStatus.ACTIVE}
        updated = self.collection_repo.update(collection_id, repository_id, updates)

        logger.info(f"Restored collection {collection_id}")
        return updated

    def _apply_inheritance(
        self,
        request: CreateCollectionRequest,
        parent_config: Dict,
        repository_id: str,
        user_id: str,
    ) -> RagCollectionConfig:
        """
        Apply inheritance rules from parent repository.

        Args:
            request: Creation request
            parent_config: Parent repository configuration
            repository_id: Repository ID
            user_id: User creating the collection

        Returns:
            Collection configuration with inheritance applied
        """
        # Generate collection ID
        collection_id = str(uuid4())

        # Inherit embedding model if not specified
        embedding_model = request.embeddingModel or parent_config.get("embeddingModelId", "")

        # Inherit allowed groups if not specified
        allowed_groups = request.allowedGroups
        if allowed_groups is None or len(allowed_groups) == 0:
            allowed_groups = parent_config.get("allowedGroups", [])

        # Inherit chunking strategy if not specified
        chunking_strategy = request.chunkingStrategy
        if chunking_strategy is None and parent_config.get("pipelines"):
            # Get chunking strategy from first pipeline
            first_pipeline = parent_config["pipelines"][0]
            # TODO: Convert pipeline config to chunking strategy
            # For now, leave as None
            pass

        # Merge metadata with parent
        parent_metadata = parent_config.get("metadata")
        if parent_metadata:
            parent_meta = CollectionMetadata(**parent_metadata)
            merged_metadata = CollectionMetadata.merge(parent_meta, request.metadata)
        else:
            merged_metadata = request.metadata

        # Create collection configuration
        now = datetime.now(timezone.utc)
        return RagCollectionConfig(
            collectionId=collection_id,
            repositoryId=repository_id,
            name=request.name,
            description=request.description,
            embeddingModel=embedding_model,
            chunkingStrategy=chunking_strategy,
            allowChunkingOverride=request.allowChunkingOverride,
            metadata=merged_metadata,
            allowedGroups=allowed_groups,
            createdBy=user_id,
            createdAt=now,
            updatedAt=now,
            status=CollectionStatus.ACTIVE,
            private=request.private,
            pipelines=request.pipelines or [],
        )

    def _delete_embeddings_from_vector_store(
        self, docs: List, repository_id: str, collection_id: str
    ) -> None:
        """
        Delete document embeddings from the vector store.

        Args:
            docs: List of documents with subdoc IDs
            repository_id: Repository ID
            collection_id: Collection ID
        """
        try:
            from repository.embeddings import RagEmbeddings
            from utilities.vector_store import get_vector_store_client

            # Collect all subdoc IDs to delete
            subdoc_ids = []
            for doc in docs:
                if hasattr(doc, 'subdocs') and doc.subdocs:
                    subdoc_ids.extend(doc.subdocs)

            if not subdoc_ids:
                logger.info("No subdocuments to delete from vector store")
                return

            # Get vector store client
            embeddings = RagEmbeddings(model_name=collection_id)
            vector_store = get_vector_store_client(
                repository_id,
                index=collection_id,
                embeddings=embeddings,
            )

            # Delete embeddings in batches to avoid overwhelming the vector store
            batch_size = 100
            for i in range(0, len(subdoc_ids), batch_size):
                batch = subdoc_ids[i:i + batch_size]
                try:
                    vector_store.delete(batch)
                    logger.info(f"Deleted {len(batch)} embeddings from vector store")
                except Exception as e:
                    logger.error(f"Failed to delete embedding batch: {e}")
                    # Continue with next batch

        except Exception as e:
            logger.error(f"Error deleting embeddings from vector store: {e}")
            raise

    def _can_user_access_collection(
        self, user_id: str, user_groups: List[str], collection: RagCollectionConfig
    ) -> bool:
        """
        Check if user can access a collection (for filtering).

        Args:
            user_id: User ID
            user_groups: User's group memberships
            collection: Collection to check

        Returns:
            True if user can access the collection
        """
        # Private collections only accessible to owner
        if collection.private and collection.createdBy != user_id:
            return False

        # Check group membership
        if not collection.allowedGroups or len(collection.allowedGroups) == 0:
            return True  # Public access

        # Check intersection
        user_groups_set = set(user_groups)
        allowed_groups_set = set(collection.allowedGroups)
        return bool(user_groups_set & allowed_groups_set)
