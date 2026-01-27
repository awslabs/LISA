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

"""Authorization provider abstraction for pluggable auth implementations."""
import logging
import os
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class AuthorizationProvider(ABC):
    """Abstract base class for authorization providers.

    This abstraction allows swapping between different authorization backends
    (e.g., OIDC group-based, BRASS bindle lock) without changing the consuming code.
    """

    @abstractmethod
    def check_admin_access(self, username: str, groups: list[str] | None = None) -> bool:
        """Check if a user has admin access.

        Parameters
        ----------
        username : str
            The username to check admin access for
        groups : list[str] | None
            Optional list of groups the user belongs to (used by group-based providers)

        Returns
        -------
        bool
            True if user has admin access, False otherwise
        """
        pass

    @abstractmethod
    def check_app_access(self, username: str, groups: list[str] | None = None) -> bool:
        """Check if a user has general application access.

        Parameters
        ----------
        username : str
            The username to check app access for
        groups : list[str] | None
            Optional list of groups the user belongs to (used by group-based providers)

        Returns
        -------
        bool
            True if user has app access, False otherwise
        """
        pass


class OIDCAuthorizationProvider(AuthorizationProvider):
    """OIDC group-based authorization provider.

    Uses JWT group claims to determine admin and app access.
    """

    def __init__(self, admin_group: str | None = None, user_group: str | None = None):
        """Initialize the OIDC authorization provider.

        Parameters
        ----------
        admin_group : str | None
            The admin group name. If not provided, uses ADMIN_GROUP env var at check time.
        user_group : str | None
            The user group name. If not provided, uses USER_GROUP env var at check time.
        """
        self._admin_group = admin_group
        self._user_group = user_group

    @property
    def admin_group(self) -> str:
        """Get admin group, reading from env if not explicitly set."""
        return self._admin_group if self._admin_group is not None else os.environ.get("ADMIN_GROUP", "")

    @property
    def user_group(self) -> str:
        """Get user group, reading from env if not explicitly set."""
        return self._user_group if self._user_group is not None else os.environ.get("USER_GROUP", "")

    def check_admin_access(self, username: str, groups: list[str] | None = None) -> bool:
        """Check if user has admin access based on group membership.

        Parameters
        ----------
        username : str
            The username (not used for group-based auth, but required by interface)
        groups : list[str] | None
            List of groups the user belongs to

        Returns
        -------
        bool
            True if user is in admin group, False otherwise
        """
        if not groups:
            logger.debug(f"No groups provided for user {username}")
            return False

        is_admin = self.admin_group in groups
        logger.info(f"User groups: {groups} and admin: {self.admin_group}")
        return is_admin

    def check_app_access(self, username: str, groups: list[str] | None = None) -> bool:
        """Check if user has app access based on group membership.

        Parameters
        ----------
        username : str
            The username (not used for group-based auth, but required by interface)
        groups : list[str] | None
            List of groups the user belongs to

        Returns
        -------
        bool
            True if user is in user group (or no user group configured), False otherwise
        """
        # If no user group is configured, allow all authenticated users
        if not self.user_group:
            return True

        if not groups:
            logger.debug(f"No groups provided for user {username}")
            return False

        has_access = self.user_group in groups
        logger.info(
            f"User {username} app access check: groups={groups}, user_group={self.user_group}, result={has_access}"
        )
        return has_access


# Singleton instance for the authorization provider
_auth_provider: AuthorizationProvider | None = None


def get_authorization_provider() -> AuthorizationProvider:
    """Get the configured authorization provider instance.

    Returns
    -------
    AuthorizationProvider
        The authorization provider instance (OIDC-based for LISA)
    """
    global _auth_provider
    if _auth_provider is None:
        _auth_provider = OIDCAuthorizationProvider()
    return _auth_provider


def set_authorization_provider(provider: AuthorizationProvider) -> None:
    """Set a custom authorization provider (useful for testing).

    Parameters
    ----------
    provider : AuthorizationProvider
        The authorization provider to use
    """
    global _auth_provider
    _auth_provider = provider
