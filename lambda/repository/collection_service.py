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

import heapq
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import boto3
from models.domain_objects import (
    CollectionMetadata,
    CollectionSortBy,
    CollectionStatus,
    IngestionJob,
    IngestionStatus,
    JobActionType,
    RagCollectionConfig,
    SortOrder,
    SortParams,
    VectorStoreStatus,
)
from repository.collection_repo import CollectionRepository
from repository.ingestion_job_repo import IngestionJobRepository
from repository.ingestion_service import DocumentIngestionService
from repository.rag_document_repo import RagDocumentRepository
from repository.vector_store_repo import VectorStoreRepository
from utilities.repository_types import RepositoryType
from utilities.validation import ValidationError

logger = logging.getLogger(__name__)

# Initialize AWS clients
sfn_client = boto3.client("stepfunctions")
ssm_client = boto3.client("ssm")


class CollectionService:
    """Service for collection operations."""

    def __init__(
        self,
        collection_repo: Optional[CollectionRepository] = None,
        vector_store_repo: Optional[VectorStoreRepository] = None,
        document_repo: Optional[RagDocumentRepository] = None,
    ):
        self.collection_repo = collection_repo or CollectionRepository()
        self.vector_store_repo = vector_store_repo or VectorStoreRepository()
        self.document_repo = document_repo or RagDocumentRepository(
            os.environ["RAG_DOCUMENT_TABLE"], os.environ["RAG_SUB_DOCUMENT_TABLE"]
        )

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

        # Private collections are only accessible to creator and admins
        if collection.private:
            return False

        # Public collection (empty allowedGroups means accessible to all)
        allowed_groups = collection.allowedGroups or []
        if not allowed_groups:
            return True

        # Check if user has at least one matching group
        if bool(set(user_groups) & set(allowed_groups)):
            return True

        return False

    def create_collection(
        self,
        repository: dict,
        collection: RagCollectionConfig,
        username: str,
    ) -> RagCollectionConfig:
        """Create a new collection with name uniqueness validation.

        Args:
            repository: Repository configuration dictionary
            collection: Collection configuration to create
            username: Username creating the collection

        Returns:
            Created collection

        Raises:
            ValidationError: If collection name already exists in repository
        """
        if repository.get("type") is RepositoryType.BEDROCK_KB:
            raise ValidationError(f"Unsupported repository type: {RepositoryType.BEDROCK_KB}")

        # Check if collection name already exists in this repository
        existing = self.collection_repo.find_by_name(collection.repositoryId, collection.name)
        if existing:
            raise ValidationError(
                f"Collection with name '{collection.name}' already exists in repository '{collection.repositoryId}'"
            )

        # Set fields
        collection.createdBy = username

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
            username: Username for access control
            user_groups: User groups for access control
            is_admin: Whether user is admin
        """
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

        # On first page, check if default collection needs to be added
        if not last_evaluated_key:
            default_collection = self.create_default_collection(repository_id=repository_id)
            if default_collection:
                # Check if a collection with the default embedding model ID already exists
                existing_ids = {c.collectionId for c in filtered}
                if default_collection.collectionId not in existing_ids:
                    filtered.append(default_collection)

        return filtered, key

    def create_default_collection(
        self, repository_id: str, repository: Optional[dict] = None
    ) -> Optional[RagCollectionConfig]:
        """
        Create a virtual default collection for a repository.

        This collection is not persisted to the database but represents the repository's
        default embedding model configuration.

        Args:
            repository_id: Repository ID

        Returns:
            Default collection config or None if repository has no embedding model
        """
        try:
            # Get repository configuration
            repository = (
                self.vector_store_repo.find_repository_by_id(repository_id=repository_id)
                if repository is None
                else repository
            )
            if not repository:
                logger.warning(f"Repository {repository_id} not found")
                return None

            active = repository.get("status", VectorStoreStatus.UNKNOWN) in [
                VectorStoreStatus.CREATE_COMPLETE,
                VectorStoreStatus.UPDATE_COMPLETE,
                VectorStoreStatus.UPDATE_COMPLETE_CLEANUP_IN_PROGRESS,
                VectorStoreStatus.UPDATE_IN_PROGRESS,
            ]
            if not active:
                logger.info(f"Repository {repository_id} is not active")
                return None

            embedding_model = repository.get("embeddingModelId")
            if not embedding_model:
                logger.info(f"Repository {repository_id} has no default embedding model")
                return None

            default_collection = RagCollectionConfig(
                collectionId=embedding_model,  # Use embedding model name as collection ID
                repositoryId=repository_id,
                name=f"{repository_id}-{embedding_model}",
                description="Default collection using repository's embedding model",
                embeddingModel=embedding_model,
                chunkingStrategy=repository.get("chunkingStrategy"),
                allowedGroups=repository.get("allowedGroups", []),
                createdBy=repository.get("createdBy", "system"),
                status="ACTIVE",
                private=False,
                metadata=CollectionMetadata(tags=["default"], customFields={}),
                allowChunkingOverride=True,
                pipelines=[],
                default=True,  # Mark as default collection
            )

            logger.info(f"Created virtual default collection for repository {repository_id}")
            return default_collection

        except Exception as e:
            logger.error(f"Failed to create default collection for repository {repository_id}: {e}")
            return None

    def update_collection(
        self,
        collection_id: str,
        repository_id: str,
        request: Any,
        username: str,
        user_groups: List[str],
        is_admin: bool,
    ) -> RagCollectionConfig:
        """Update a collection with access control and name uniqueness validation.

        Args:
            collection_id: Collection ID to update
            repository_id: Repository ID
            request: RagCollectionConfig with fields to update
            username: Username for access control
            user_groups: User groups for access control
            is_admin: Whether user is admin

        Returns:
            Updated collection

        Raises:
            ValidationError: If name already exists or access denied
        """
        collection = self.collection_repo.find_by_id(collection_id, repository_id)
        if not collection:
            raise ValidationError(f"Collection {collection_id} not found")
        if not self.has_access(collection, username, user_groups, is_admin, require_write=True):
            raise ValidationError(f"Permission denied to update collection {collection_id}")

        # Define updatable fields
        updatable_fields = [
            "name",
            "description",
            "chunkingStrategy",
            "allowedGroups",
            "metadata",
            "private",
            "allowChunkingOverride",
            "pipelines",
        ]

        # Build updates dictionary from request
        updates = {
            field: getattr(request, field)
            for field in updatable_fields
            if hasattr(request, field) and getattr(request, field) is not None
        }

        # Special validation for name changes
        if "name" in updates and updates["name"] != collection.name:
            existing = self.collection_repo.find_by_name(repository_id, updates["name"])
            if existing and existing.collectionId != collection_id:
                raise ValidationError(
                    f"Collection with name '{updates['name']}' already exists in repository '{repository_id}'"
                )

        # Update collection
        updated = self.collection_repo.update(collection_id, repository_id, updates)
        return updated

    def delete_collection(
        self,
        repository_id: str,
        collection_id: Optional[str],
        embedding_name: Optional[str],
        username: str,
        user_groups: List[str],
        is_admin: bool,
    ) -> Dict[str, Any]:
        """Delete a collection with access control.

        Args:
            repository_id: Repository ID
            collection_id: Collection ID (None for default collections)
            embedding_name: Embedding model name (None for regular collections)
            username: Username for access control
            user_groups: User groups for access control
            is_admin: Whether user is admin

        Returns:
            Dictionary with deletion type and job ID
        """
        # Validate that at least one identifier is provided
        if not collection_id and not embedding_name:
            raise ValidationError("Either collection_id or embedding_name must be provided")

        # Determine deletion type
        is_default_collection = embedding_name is not None
        deletion_type = "partial" if is_default_collection else "full"

        logger.info(
            f"Starting {deletion_type} deletion for repository {repository_id}, "
            f"collection_id={collection_id}, embedding_name={embedding_name}"
        )

        # For regular collections, verify access and update status
        if not is_default_collection:
            collection = self.collection_repo.find_by_id(collection_id, repository_id)
            if not collection:
                raise ValidationError(f"Collection {collection_id} not found")
            if not self.has_access(collection, username, user_groups, is_admin, require_write=True):
                raise ValidationError(f"Permission denied to delete collection {collection_id}")

            # Update collection status to DELETE_IN_PROGRESS
            self.collection_repo.update(collection_id, repository_id, {"status": CollectionStatus.DELETE_IN_PROGRESS})

            embedding_model = None  # Don't set embedding_model for regular collections
        else:
            # For default collections, use embedding_name directly
            embedding_model = embedding_name

        # Create deletion job
        try:
            ingestion_job_repo = IngestionJobRepository()
            ingestion_service = DocumentIngestionService()

            deletion_job = IngestionJob(
                repository_id=repository_id,
                collection_id=collection_id if not is_default_collection else None,
                s3_path="",  # Not applicable for collection deletion
                embedding_model=embedding_model,  # Only set for default collections
                username=username,
                status=IngestionStatus.DELETE_PENDING,
                job_type=JobActionType.COLLECTION_DELETION,
                collection_deletion=True,
            )

            # Save and submit the deletion job
            ingestion_job_repo.save(deletion_job)
            ingestion_service.create_delete_job(deletion_job)

            logger.info(f"Submitted {deletion_type} deletion job {deletion_job.id} " f"for repository {repository_id}")

            return {
                "jobId": deletion_job.id,
                "deletionType": deletion_type,
                "status": deletion_job.status,
            }

        except Exception as e:
            logger.error(f"Failed to submit deletion job: {e}", exc_info=True)

            # Update collection status to DELETE_FAILED (only for regular collections)
            if not is_default_collection:
                self.collection_repo.update(collection_id, repository_id, {"status": CollectionStatus.DELETE_FAILED})

            raise

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

    def list_all_user_collections(
        self,
        username: str,
        user_groups: List[str],
        is_admin: bool,
        page_size: int = 20,
        pagination_token: Optional[Dict[str, Any]] = None,
        filter_text: Optional[str] = None,
        sort_params: Optional[SortParams] = None,
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        List all collections user has access to across all repositories.

        This method orchestrates the complete workflow:
        1. Get accessible repositories
        2. Estimate collection count
        3. Select pagination strategy
        4. Execute query and return results

        Args:
            username: Username for access control
            user_groups: User groups for access control
            is_admin: Whether user is admin
            page_size: Number of items per page
            pagination_token: Pagination token from previous request
            filter_text: Optional text filter for name/description
            sort_params: Optional SortParams object for sorting (defaults to createdAt desc)

        Returns:
            Tuple of (list of enriched collections, pagination token)
        """
        # Use default sort params if not provided
        if sort_params is None:
            sort_params = SortParams(sort_by=CollectionSortBy.CREATED_AT, sort_order=SortOrder.DESC)

        logger.info(
            f"Listing all user collections for user={username}, is_admin={is_admin}, "
            f"page_size={page_size}, filter={filter_text}, sort_by={sort_params.sort_by.value}"
        )

        # Get repositories user can access
        repositories = self._get_accessible_repositories(username, user_groups, is_admin)
        logger.debug(f"User has access to {len(repositories)} repositories")

        if not repositories:
            logger.info("User has no accessible repositories, returning empty list")
            return [], None

        # Estimate total collections
        estimated_total = self._estimate_total_collections(repositories)
        logger.info(f"Estimated total collections: {estimated_total}")

        # Select and execute pagination strategy
        if estimated_total > 1000:
            logger.info("Using scalable pagination strategy for large dataset")
            collections, next_token = self._paginate_large_collections(
                repositories, username, user_groups, is_admin, page_size, pagination_token, filter_text, sort_params
            )
        else:
            logger.info("Using simple pagination strategy")
            collections, next_token = self._paginate_collections(
                repositories, username, user_groups, is_admin, page_size, pagination_token, filter_text, sort_params
            )

        logger.info(f"Returning {len(collections)} collections")
        return collections, next_token

    def _get_accessible_repositories(
        self, username: str, user_groups: List[str], is_admin: bool
    ) -> List[Dict[str, Any]]:
        """
        Get all repositories user has access to.

        Args:
            username: Username for access control
            user_groups: User groups for access control
            is_admin: Whether user is admin

        Returns:
            List of repository configurations user can access
        """
        all_repos = self.vector_store_repo.get_registered_repositories()

        if is_admin:
            logger.debug(f"Admin user has access to all {len(all_repos)} repositories")
            return all_repos

        accessible = [repo for repo in all_repos if self._has_repository_access(user_groups, repo)]
        logger.debug(f"User has access to {len(accessible)} of {len(all_repos)} repositories")
        return accessible

    def _has_repository_access(self, user_groups: List[str], repository: Dict[str, Any]) -> bool:
        """
        Check if user has access to repository based on groups.

        Args:
            user_groups: User groups for access control
            repository: Repository configuration

        Returns:
            True if user has access, False otherwise
        """
        allowed_groups = repository.get("allowedGroups", [])

        # Public repository (no group restrictions)
        if not allowed_groups:
            return True

        # Check if user has at least one matching group
        has_access = bool(set(user_groups) & set(allowed_groups))
        logger.debug(
            f"Repository {repository.get('repositoryId')} access check: "
            f"user_groups={user_groups}, allowed_groups={allowed_groups}, has_access={has_access}"
        )
        return has_access

    def _enrich_with_repository_metadata(
        self, collections: List[RagCollectionConfig], repositories: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Enrich collections with repository metadata.

        Args:
            collections: List of collection configurations
            repositories: List of repository configurations

        Returns:
            List of enriched collection dictionaries with repositoryName
        """
        # Create repository lookup map
        repo_map = {repo["repositoryId"]: repo for repo in repositories}

        enriched = []
        for collection in collections:
            collection_dict = collection.model_dump(mode="json")

            # Add repository name
            repo_id = collection.repositoryId
            repository = repo_map.get(repo_id)
            if repository:
                collection_dict["repositoryName"] = repository.get("repositoryName", repo_id)
            else:
                # Fallback if repository not in map
                logger.warning(f"Repository {repo_id} not found in accessible repositories")
                collection_dict["repositoryName"] = repo_id

            enriched.append(collection_dict)

        return enriched

    def _estimate_total_collections(self, repositories: List[Dict[str, Any]]) -> int:
        """
        Estimate total number of collections across repositories.

        Args:
            repositories: List of repository configurations

        Returns:
            Estimated total collection count
        """
        total = 0
        for repo in repositories:
            try:
                count = self.collection_repo.count_by_repository(repo["repositoryId"])
                total += count
            except Exception as e:
                logger.warning(f"Failed to count collections for repository {repo['repositoryId']}: {e}")
                # Continue with other repositories

        return total

    def _paginate_collections(
        self,
        repositories: List[Dict[str, Any]],
        username: str,
        user_groups: List[str],
        is_admin: bool,
        page_size: int,
        pagination_token: Optional[Dict[str, Any]],
        filter_text: Optional[str],
        sort_params: SortParams,
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Simple pagination strategy for small-to-medium deployments.

        Aggregates all collections in memory, applies filtering and sorting,
        then returns requested page.

        Args:
            repositories: List of accessible repositories
            username: Username for access control
            user_groups: User groups for access control
            is_admin: Whether user is admin
            page_size: Number of items per page
            pagination_token: Pagination token from previous request
            filter_text: Optional text filter
            sort_params: SortParams object for sorting

        Returns:
            Tuple of (list of enriched collections, next pagination token)
        """
        # Parse pagination token
        offset = 0
        if pagination_token and pagination_token.get("version") == "v1":
            offset = pagination_token.get("offset", 0)
            # Verify filter consistency
            token_filter = pagination_token.get("filters", {})
            if (
                token_filter.get("filter") != filter_text
                or token_filter.get("sortBy") != sort_params.sort_by
                or token_filter.get("sortOrder") != sort_params.sort_order
            ):
                logger.warning("Pagination token filters don't match request, resetting to offset 0")
                offset = 0

        # Aggregate all collections from accessible repositories
        all_collections: List[RagCollectionConfig] = []

        for repo in repositories:
            repo_id = repo["repositoryId"]
            try:
                # Query collections for this repository (fetch up to 100 per repo)
                collections, _ = self.collection_repo.list_by_repository(
                    repository_id=repo_id,
                    page_size=100,
                    last_evaluated_key=None,
                )

                # Filter by collection-level permissions
                accessible = [c for c in collections if self.has_access(c, username, user_groups, is_admin)]

                # Check if default collection needs to be added
                default_collection = self.create_default_collection(repo_id, repo)
                if default_collection:
                    # Check if a collection with the default embedding model ID already exists
                    existing_ids = {c.collectionId for c in accessible}
                    if default_collection.collectionId not in existing_ids:
                        accessible.append(default_collection)

                all_collections.extend(accessible)
                logger.debug(f"Repository {repo_id}: {len(accessible)} accessible collections")

            except Exception as e:
                logger.error(f"Failed to query collections for repository {repo_id}: {e}")
                # Continue with other repositories

        # Apply text filtering
        if filter_text:
            all_collections = [c for c in all_collections if self._matches_filter(c, filter_text)]
            logger.debug(f"After filtering: {len(all_collections)} collections")

        # Apply sorting
        all_collections = self._sort_collections(all_collections, sort_params)

        # Apply pagination
        start_idx = offset
        end_idx = start_idx + page_size
        page_collections = all_collections[start_idx:end_idx]

        # Enrich with repository metadata
        enriched = self._enrich_with_repository_metadata(page_collections, repositories)

        # Build next token if more pages exist
        next_token = None
        if end_idx < len(all_collections):
            next_token = {
                "version": "v1",
                "offset": end_idx,
                "filters": {
                    "filter": filter_text,
                    "sortBy": sort_params.sort_by.value,
                    "sortOrder": sort_params.sort_order.value,
                },
            }

        return enriched, next_token

    def _matches_filter(self, collection: RagCollectionConfig, filter_text: str) -> bool:
        """
        Check if collection matches text filter.

        Args:
            collection: Collection to check
            filter_text: Text to search for (case-insensitive)

        Returns:
            True if collection name or description contains filter text
        """
        filter_lower = filter_text.lower()

        # Check name
        if collection.name and filter_lower in collection.name.lower():
            return True

        # Check description
        if collection.description and filter_lower in collection.description.lower():
            return True

        return False

    def _sort_collections(
        self, collections: List[RagCollectionConfig], sort_params: SortParams
    ) -> List[RagCollectionConfig]:
        """
        Sort collections by specified field and order.

        Args:
            collections: List of collections to sort
            sort_params: SortParams object containing sort field and order

        Returns:
            Sorted list of collections
        """
        reverse = sort_params.sort_order == SortOrder.DESC

        if sort_params.sort_by == CollectionSortBy.NAME:
            return sorted(collections, key=lambda c: c.name or "", reverse=reverse)
        elif sort_params.sort_by == CollectionSortBy.UPDATED_AT:
            return sorted(collections, key=lambda c: c.updatedAt, reverse=reverse)
        else:  # Default to createdAt
            return sorted(collections, key=lambda c: c.createdAt, reverse=reverse)

    def _paginate_large_collections(
        self,
        repositories: List[Dict[str, Any]],
        username: str,
        user_groups: List[str],
        is_admin: bool,
        page_size: int,
        pagination_token: Optional[Dict[str, Any]],
        filter_text: Optional[str],
        sort_params: SortParams,
    ) -> Tuple[List[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Scalable pagination strategy for large deployments.

        Uses incremental merge with per-repository cursors to handle
        1000+ collections efficiently without loading all into memory.

        Args:
            repositories: List of accessible repositories
            username: Username for access control
            user_groups: User groups for access control
            is_admin: Whether user is admin
            page_size: Number of items per page
            pagination_token: Pagination token from previous request
            filter_text: Optional text filter
            sort_params: SortParams object for sorting

        Returns:
            Tuple of (list of enriched collections, next pagination token)
        """
        # Initialize or restore repository cursors
        if pagination_token and pagination_token.get("version") == "v2":
            cursors = pagination_token.get("repositoryCursors", {})
            global_offset = pagination_token.get("globalOffset", 0)
            # Convert lists back to sets
            seen_ids_raw = pagination_token.get("seenCollectionIds", {})
            seen_collection_ids = {repo_id: set(id_list) for repo_id, id_list in seen_ids_raw.items()}

            # Verify filter consistency
            token_filters = pagination_token.get("filters", {})
            if (
                token_filters.get("filter") != filter_text
                or token_filters.get("sortBy") != sort_params.sort_by.value
                or token_filters.get("sortOrder") != sort_params.sort_order.value
            ):
                logger.warning("Pagination token filters don't match, resetting cursors")
                cursors = {}
                global_offset = 0
                seen_collection_ids = {}
        else:
            cursors = {}
            global_offset = 0
            seen_collection_ids = {}

        # Initialize cursors for new repositories
        for repo in repositories:
            repo_id = repo["repositoryId"]
            if repo_id not in cursors:
                cursors[repo_id] = {"lastEvaluatedKey": None, "exhausted": False}
            if repo_id not in seen_collection_ids:
                seen_collection_ids[repo_id] = set()

        # Fetch batches from each non-exhausted repository
        batches = []
        for repo in repositories:
            repo_id = repo["repositoryId"]
            cursor = cursors[repo_id]

            if cursor["exhausted"]:
                continue

            try:
                # Query collections for this repository
                collections, next_key = self.collection_repo.list_by_repository(
                    repository_id=repo_id,
                    page_size=page_size,  # Fetch page_size per repo
                    last_evaluated_key=cursor["lastEvaluatedKey"],
                )

                # Filter by collection-level permissions
                accessible = [c for c in collections if self.has_access(c, username, user_groups, is_admin)]

                # Track seen collection IDs for this repository
                for c in accessible:
                    seen_collection_ids[repo_id].add(c.collectionId)

                # On first fetch for this repository, check if default collection needs to be added
                if not cursor["lastEvaluatedKey"]:
                    default_collection = self.create_default_collection(repo_id, repo)
                    if default_collection:
                        # Check if we've seen a collection with the default embedding model ID
                        if default_collection.collectionId not in seen_collection_ids[repo_id]:
                            accessible.append(default_collection)
                            seen_collection_ids[repo_id].add(default_collection.collectionId)

                # Apply text filtering
                if filter_text:
                    accessible = [c for c in accessible if self._matches_filter(c, filter_text)]

                batches.append({"repositoryId": repo_id, "collections": accessible, "nextKey": next_key})

                # Update cursor
                cursors[repo_id]["lastEvaluatedKey"] = next_key
                cursors[repo_id]["exhausted"] = next_key is None

                logger.debug(
                    f"Repository {repo_id}: fetched {len(accessible)} collections, "
                    f"exhausted={cursors[repo_id]['exhausted']}"
                )

            except Exception as e:
                logger.error(f"Failed to query collections for repository {repo_id}: {e}")
                cursors[repo_id]["exhausted"] = True

        # Merge batches using heap for efficient sorting
        merged = self._merge_sorted_batches(batches, sort_params.sort_by.value, sort_params.sort_order.value)

        # Extract requested page
        start_idx = global_offset
        end_idx = start_idx + page_size
        page_collections = merged[start_idx:end_idx]

        # Enrich with repository metadata
        enriched = self._enrich_with_repository_metadata(page_collections, repositories)

        # Determine if more pages exist
        has_more = (end_idx < len(merged)) or any(not c["exhausted"] for c in cursors.values())

        # Build next token
        next_token = None
        if has_more:
            # If we consumed all merged results, reset offset for next fetch
            new_offset = end_idx if end_idx < len(merged) else 0

            # Convert sets to lists for JSON serialization
            serializable_seen_ids = {repo_id: list(id_set) for repo_id, id_set in seen_collection_ids.items()}

            next_token = {
                "version": "v2",
                "repositoryCursors": cursors,
                "globalOffset": new_offset,
                "seenCollectionIds": serializable_seen_ids,
                "filters": {
                    "filter": filter_text,
                    "sortBy": sort_params.sort_by.value,
                    "sortOrder": sort_params.sort_order.value,
                },
            }

        return enriched, next_token

    def _merge_sorted_batches(
        self, batches: List[Dict[str, Any]], sort_by: str, sort_order: str
    ) -> List[RagCollectionConfig]:
        """
        Merge pre-sorted batches from multiple repositories using min-heap.

        Time Complexity: O(N log K) where N = total collections, K = number of repositories
        Space Complexity: O(N) for merged result

        Args:
            batches: List of batch dictionaries with collections from each repository
            sort_by: Field to sort by
            sort_order: Sort order (asc/desc)

        Returns:
            Merged and sorted list of collections
        """
        if not batches:
            return []

        # Create heap with first item from each batch
        heap: List[Tuple[Any, str, int, Dict[str, Any]]] = []

        for batch in batches:
            if batch["collections"]:
                collection = batch["collections"][0]
                sort_key = self._get_sort_key(collection, sort_by)

                # For descending order, negate numeric keys or reverse string comparison
                if sort_order.lower() == "desc":
                    if isinstance(sort_key, str):
                        # For strings, we'll reverse the final list instead
                        pass
                    else:
                        # For datetime/numeric, negate for heap
                        sort_key = -sort_key.timestamp() if hasattr(sort_key, "timestamp") else -sort_key

                heapq.heappush(heap, (sort_key, batch["repositoryId"], 0, batch))

        merged = []
        while heap:
            _, repo_id, idx, batch = heapq.heappop(heap)
            merged.append(batch["collections"][idx])

            # Add next item from same batch
            next_idx = idx + 1
            if next_idx < len(batch["collections"]):
                next_collection = batch["collections"][next_idx]
                next_sort_key = self._get_sort_key(next_collection, sort_by)

                if sort_order.lower() == "desc":
                    if isinstance(next_sort_key, str):
                        pass
                    else:
                        next_sort_key = (
                            -next_sort_key.timestamp() if hasattr(next_sort_key, "timestamp") else -next_sort_key
                        )

                heapq.heappush(heap, (next_sort_key, repo_id, next_idx, batch))

        # For descending string sorts, reverse the final list
        if sort_order.lower() == "desc" and sort_by == "name":
            merged.reverse()

        return merged

    def _get_sort_key(self, collection: RagCollectionConfig, sort_by: str) -> Any:
        """
        Extract sort key from collection.

        Args:
            collection: Collection to extract key from
            sort_by: Field to sort by

        Returns:
            Sort key value
        """
        if sort_by == "name":
            return collection.name or ""
        elif sort_by == "updatedAt":
            return collection.updatedAt
        else:  # Default to createdAt
            return collection.createdAt
