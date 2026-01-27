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

"""Authorization provider abstraction for pluggable auth implementations.

This module provides a plugin architecture for authorization providers. External
packages can register custom providers by calling `register_authorization_provider()`.

Plugin Registration:
    Plugins should register themselves on import. For Lambda layers, create a module
    that registers the provider when imported:

    ```python
    # my_auth_plugin/__init__.py
    from utilities.auth_provider import register_authorization_provider
    from .my_provider import MyAuthorizationProvider

    register_authorization_provider('my_provider', MyAuthorizationProvider, default=True)
    ```

    Then ensure the plugin is imported at Lambda startup (e.g., via a Lambda layer
    that's automatically loaded).
"""
import logging
import os
from abc import ABC, abstractmethod
from typing import Type

logger = logging.getLogger(__name__)


class AuthorizationProvider(ABC):
    """Abstract base class for authorization providers.

    This abstraction allows swapping between different authorization backends
    (e.g., OIDC group-based, custom auth) without changing the consuming code.

    To create a custom provider:
    1. Subclass AuthorizationProvider
    2. Implement check_admin_access() and check_app_access()
    3. Register with register_authorization_provider()
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
        logger.info(f"User {username} app access check: groups={groups}, user_group={self.user_group}, result={has_access}")
        return has_access


# ============================================================================
# Plugin Registry
# ============================================================================

# Registry of available authorization providers
_provider_registry: dict[str, Type[AuthorizationProvider]] = {}

# The default provider name to use when AUTH_PROVIDER env var is not set
_default_provider_name: str = "oidc"

# Cached singleton instance of the current authorization provider
_auth_provider: AuthorizationProvider | None = None


def register_authorization_provider(
    name: str,
    provider_class: Type[AuthorizationProvider],
    default: bool = False
) -> None:
    """Register an authorization provider plugin.

    This function allows external packages (e.g., Lambda layers) to register
    custom authorization providers. Providers registered with default=True
    will be used unless overridden by the AUTH_PROVIDER environment variable.

    Parameters
    ----------
    name : str
        Unique name for the provider (e.g., 'oidc', 'brass', 'custom')
    provider_class : Type[AuthorizationProvider]
        The provider class (not an instance) to register
    default : bool
        If True, this provider becomes the default. Later registrations
        with default=True will override earlier ones.

    Example
    -------
    ```python
    from utilities.auth_provider import (
        AuthorizationProvider,
        register_authorization_provider
    )

    class MyCustomProvider(AuthorizationProvider):
        def check_admin_access(self, username, groups=None):
            # Custom implementation
            return True

        def check_app_access(self, username, groups=None):
            # Custom implementation
            return True

    # Register as the default provider
    register_authorization_provider('custom', MyCustomProvider, default=True)
    ```
    """
    global _default_provider_name, _auth_provider

    _provider_registry[name] = provider_class
    logger.info(f"Registered authorization provider: {name}")

    if default:
        _default_provider_name = name
        # Clear cached instance so next get_authorization_provider() uses new default
        _auth_provider = None
        logger.info(f"Set default authorization provider to: {name}")


def get_registered_providers() -> list[str]:
    """Get list of registered provider names.

    Returns
    -------
    list[str]
        Names of all registered authorization providers
    """
    return list(_provider_registry.keys())


def get_authorization_provider() -> AuthorizationProvider:
    """Get the configured authorization provider instance.

    The provider is selected in this order:
    1. AUTH_PROVIDER environment variable (if set and registered)
    2. The default provider (set via register_authorization_provider with default=True)
    3. Falls back to 'oidc' if nothing else is configured

    Returns
    -------
    AuthorizationProvider
        The authorization provider instance

    Raises
    ------
    ValueError
        If the requested provider is not registered
    """
    global _auth_provider

    if _auth_provider is None:
        # Determine which provider to use
        provider_name = os.environ.get("AUTH_PROVIDER", _default_provider_name)

        if provider_name not in _provider_registry:
            available = ", ".join(_provider_registry.keys()) or "none"
            raise ValueError(
                f"Authorization provider '{provider_name}' is not registered. "
                f"Available providers: {available}"
            )

        provider_class = _provider_registry[provider_name]
        _auth_provider = provider_class()
        logger.info(f"Initialized authorization provider: {provider_name}")

    return _auth_provider


def set_authorization_provider(provider: AuthorizationProvider) -> None:
    """Set a custom authorization provider instance directly.

    This bypasses the registry and sets the provider instance directly.
    Useful for testing or when you need a pre-configured instance.

    Parameters
    ----------
    provider : AuthorizationProvider
        The authorization provider instance to use
    """
    global _auth_provider
    _auth_provider = provider
    logger.info(f"Set authorization provider instance: {type(provider).__name__}")


def reset_authorization_provider() -> None:
    """Reset the cached authorization provider.

    Forces the next call to get_authorization_provider() to create a new instance.
    Useful for testing or when configuration changes.
    """
    global _auth_provider
    _auth_provider = None
    logger.debug("Reset authorization provider cache")


# ============================================================================
# Register built-in providers
# ============================================================================

# Register OIDC as the default built-in provider
register_authorization_provider("oidc", OIDCAuthorizationProvider, default=True)
