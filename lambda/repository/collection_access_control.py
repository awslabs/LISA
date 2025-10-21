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

"""Collection-specific access control implementation."""

import logging
from typing import Optional

from models.domain_objects import RagCollectionConfig
from repository.collection_repo import CollectionRepository
from repository.vector_store_repo import VectorStoreRepository
from utilities.access_control import (
    AccessDecision,
    BaseAccessControlPolicy,
    CachedAccessControlService,
    Permission,
    ResourceContext,
    UserContext,
)

logger = logging.getLogger(__name__)


class CollectionAccessControlPolicy(BaseAccessControlPolicy[RagCollectionConfig]):
    """Access control policy for collections."""

    def __init__(
        self,
        collection_repo: Optional[CollectionRepository] = None,
        vector_store_repo: Optional[VectorStoreRepository] = None,
    ):
        """
        Initialize the collection access control policy.

        Args:
            collection_repo: Collection repository for database access
            vector_store_repo: Vector store repository for parent checks
        """
        self.collection_repo = collection_repo or CollectionRepository()
        self.vector_store_repo = vector_store_repo or VectorStoreRepository()

    def get_resource_context(
        self, resource_id: str, repository_id: Optional[str] = None, **kwargs
    ) -> Optional[ResourceContext]:
        """
        Get collection resource context.

        Args:
            resource_id: The collection ID
            repository_id: The repository ID (required)
            **kwargs: Additional parameters

        Returns:
            ResourceContext if found, None otherwise
        """
        if not repository_id:
            logger.error("repository_id is required for collection access control")
            return None

        try:
            collection = self.collection_repo.find_by_id(resource_id, repository_id)
            if not collection:
                return None

            return ResourceContext(
                resource_id=resource_id,
                resource_type="collection",
                allowed_groups=collection.allowedGroups,
                owner_id=collection.createdBy,
                is_private=collection.private,
                parent_id=repository_id,
                metadata={"status": collection.status},
            )
        except Exception as e:
            logger.error(f"Error getting collection context: {e}")
            return None

    def check_repository_access(self, user: UserContext, repository_id: str, permission: Permission) -> AccessDecision:
        """
        Check if user has permission for a repository (for creating collections).

        Args:
            user: User context
            repository_id: The repository ID
            permission: The permission level to check

        Returns:
            AccessDecision with the result
        """
        # Admin users have full access
        if user.is_admin:
            return AccessDecision(allowed=True, permission=permission, granting_groups=["admin"])

        try:
            # Get repository configuration
            repo_config = self.vector_store_repo.find_repository_by_id(repository_id)

            # Check if user collections are allowed for write operations
            if permission == Permission.WRITE:
                allow_user_collections = repo_config.get("allowUserCollections", True)
                if not allow_user_collections:
                    return AccessDecision(
                        allowed=False,
                        permission=permission,
                        reason="Repository does not allow user-created collections",
                    )

            # Check group membership
            allowed_groups = repo_config.get("allowedGroups", [])
            return self._check_group_access(user.groups, allowed_groups, permission)

        except ValueError as e:
            logger.error(f"Repository {repository_id} not found: {e}")
            return AccessDecision(
                allowed=False,
                permission=permission,
                reason=f"Repository '{repository_id}' not found",
            )
        except Exception as e:
            logger.error(f"Error checking repository permission: {e}")
            return AccessDecision(
                allowed=False,
                permission=permission,
                reason=f"Error checking permissions: {str(e)}",
            )


class CollectionAccessControlService:
    """High-level service for collection access control."""

    def __init__(
        self,
        collection_repo: Optional[CollectionRepository] = None,
        vector_store_repo: Optional[VectorStoreRepository] = None,
    ):
        """
        Initialize the collection access control service.

        Args:
            collection_repo: Collection repository for database access
            vector_store_repo: Vector store repository for parent checks
        """
        policy = CollectionAccessControlPolicy(collection_repo, vector_store_repo)
        self.cached_service = CachedAccessControlService(policy)
        self.policy = policy

    def check_collection_permission(
        self,
        user_id: str,
        user_groups: list[str],
        is_admin: bool,
        collection_id: str,
        repository_id: str,
        permission: Permission,
        use_cache: bool = True,
    ) -> AccessDecision:
        """
        Check if user has permission for a collection.

        Args:
            user_id: The user ID
            user_groups: The user's group memberships
            is_admin: Whether the user is an admin
            collection_id: The collection ID
            repository_id: The repository ID
            permission: The permission level to check
            use_cache: Whether to use cached decisions

        Returns:
            AccessDecision with the result
        """
        user = UserContext(user_id=user_id, groups=user_groups, is_admin=is_admin)

        # Get resource context
        resource = self.policy.get_resource_context(collection_id, repository_id=repository_id)
        if not resource:
            return AccessDecision(
                allowed=False,
                permission=permission,
                reason=f"Collection '{collection_id}' not found",
            )

        # Check access
        return self.cached_service.check_access(user, resource, permission, use_cache)

    def check_repository_permission(
        self,
        user_id: str,
        user_groups: list[str],
        is_admin: bool,
        repository_id: str,
        permission: Permission,
    ) -> AccessDecision:
        """
        Check if user has permission for a repository (for creating collections).

        Args:
            user_id: The user ID
            user_groups: The user's group memberships
            is_admin: Whether the user is an admin
            repository_id: The repository ID
            permission: The permission level to check

        Returns:
            AccessDecision with the result
        """
        user = UserContext(user_id=user_id, groups=user_groups, is_admin=is_admin)
        return self.policy.check_repository_access(user, repository_id, permission)

    def clear_cache(self) -> None:
        """Clear the entire cache."""
        self.cached_service.clear_cache()

    def clear_cache_for_collection(self, collection_id: str) -> None:
        """Clear cache entries for a specific collection."""
        self.cached_service.clear_cache_for_resource(collection_id)


def check_collection_permission(
    user_id: str,
    user_groups: list[str],
    is_admin: bool,
    collection_id: str,
    repository_id: str,
    permission: Permission,
) -> bool:
    """
    Quick permission check function for collections.

    Args:
        user_id: The user ID
        user_groups: The user's group memberships
        is_admin: Whether the user is an admin
        collection_id: The collection ID
        repository_id: The repository ID
        permission: The permission level to check

    Returns:
        True if access is allowed, False otherwise
    """
    service = CollectionAccessControlService()
    decision = service.check_collection_permission(
        user_id, user_groups, is_admin, collection_id, repository_id, permission
    )
    return decision.allowed
