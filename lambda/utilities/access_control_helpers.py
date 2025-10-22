#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Helper functions for access control."""

from typing import List
from utilities.validation import ValidationError


def user_has_access(
    username: str,
    user_groups: List[str],
    is_admin: bool,
    allowed_groups: List[str],
    owner: str,
    is_private: bool,
) -> bool:
    """Check if user has access to a resource."""
    if is_admin:
        return True
    if owner == username:
        return True
    if not is_private and check_group_access(user_groups, allowed_groups):
        return True
    return False


def validate_access(
    username: str,
    user_groups: List[str],
    is_admin: bool,
    allowed_groups: List[str],
    owner: str,
    is_private: bool,
    resource_type: str,
    resource_id: str,
) -> None:
    """Validate access and raise exception if denied."""
    if not user_has_access(username, user_groups, is_admin, allowed_groups, owner, is_private):
        raise ValidationError(f"Permission denied for {resource_type} {resource_id}")


def check_group_access(user_groups: List[str], allowed_groups: List[str]) -> bool:
    """Check if user groups intersect with allowed groups."""
    return bool(set(user_groups) & set(allowed_groups))


def is_owner(username: str, owner: str) -> bool:
    """Check if user is the owner."""
    return username == owner
