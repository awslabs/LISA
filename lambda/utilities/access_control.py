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

"""Generic access control framework for LISA resources."""

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Generic, List, Optional, TypeVar

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    """Permission levels for resources."""

    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


@dataclass
class AccessDecision:
    """Result of an access control check."""

    allowed: bool
    permission: Permission
    reason: Optional[str] = None
    granting_groups: Optional[List[str]] = None
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.granting_groups is None:
            self.granting_groups = []

    def __repr__(self) -> str:
        if self.allowed:
            return f"AccessDecision(allowed=True, permission={self.permission}, groups={self.granting_groups})"
        return f"AccessDecision(allowed=False, permission={self.permission}, reason={self.reason})"


@dataclass
class UserContext:
    """User context for access control checks."""

    user_id: str
    groups: List[str]
    is_admin: bool


@dataclass
class ResourceContext:
    """Resource context for access control checks."""

    resource_id: str
    resource_type: str
    allowed_groups: Optional[List[str]] = None
    owner_id: Optional[str] = None
    is_private: bool = False
    parent_id: Optional[str] = None
    metadata: Optional[Dict] = None


TResource = TypeVar("TResource")


class AccessControlPolicy(ABC, Generic[TResource]):
    """Abstract base class for access control policies."""

    @abstractmethod
    def check_access(self, user: UserContext, resource: ResourceContext, permission: Permission) -> AccessDecision:
        """
        Check if user has permission for resource.

        Args:
            user: User context
            resource: Resource context
            permission: Permission level to check

        Returns:
            AccessDecision with the result
        """
        pass

    @abstractmethod
    def get_resource_context(self, resource_id: str, **kwargs) -> Optional[ResourceContext]:
        """
        Get resource context for access control.

        Args:
            resource_id: The resource ID
            **kwargs: Additional parameters for resource lookup

        Returns:
            ResourceContext if found, None otherwise
        """
        pass


class BaseAccessControlPolicy(AccessControlPolicy[TResource]):
    """Base implementation of common access control logic."""

    def check_access(self, user: UserContext, resource: ResourceContext, permission: Permission) -> AccessDecision:
        """
        Check if user has permission for resource.

        Implements common access control logic:
        1. Admin override
        2. Owner check (for private resources)
        3. Group membership check

        Args:
            user: User context
            resource: Resource context
            permission: Permission level to check

        Returns:
            AccessDecision with the result
        """
        # Admin users have full access
        if user.is_admin:
            logger.info(
                f"Admin user {user.user_id} granted {permission} access to "
                f"{resource.resource_type} {resource.resource_id}"
            )
            return AccessDecision(allowed=True, permission=permission, granting_groups=["admin"])

        # Check if resource is private
        if resource.is_private:
            if resource.owner_id and resource.owner_id != user.user_id:
                logger.info(
                    f"User {user.user_id} denied {permission} access to private "
                    f"{resource.resource_type} {resource.resource_id}"
                )
                return AccessDecision(
                    allowed=False,
                    permission=permission,
                    reason=f"{resource.resource_type.capitalize()} is private and user is not the owner",
                )

        # Check group membership
        decision = self._check_group_access(user.groups, resource.allowed_groups, permission)

        logger.info(
            f"User {user.user_id} {'granted' if decision.allowed else 'denied'} {permission} "
            f"access to {resource.resource_type} {resource.resource_id}"
        )

        return decision

    def _check_group_access(
        self, user_groups: List[str], allowed_groups: Optional[List[str]], permission: Permission
    ) -> AccessDecision:
        """
        Check if user's groups grant access.

        Args:
            user_groups: The user's group memberships
            allowed_groups: The resource's allowed groups
            permission: The permission level

        Returns:
            AccessDecision with the result
        """
        # If no groups specified, allow access to everyone
        if not allowed_groups or len(allowed_groups) == 0:
            return AccessDecision(allowed=True, permission=permission, granting_groups=["public"])

        # Check for group intersection
        user_groups_set = set(user_groups)
        allowed_groups_set = set(allowed_groups)
        granting_groups = list(user_groups_set & allowed_groups_set)

        if granting_groups:
            return AccessDecision(allowed=True, permission=permission, granting_groups=granting_groups)

        return AccessDecision(
            allowed=False,
            permission=permission,
            reason=f"User groups {user_groups} do not intersect with allowed groups {allowed_groups}",
        )
