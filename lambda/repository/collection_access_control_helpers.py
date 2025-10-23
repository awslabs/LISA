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

#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Helper functions for collection access control."""

from typing import List

from models.domain_objects import RagCollectionConfig
from utilities.validation import ValidationError


def can_access_collection(
    collection: RagCollectionConfig,
    username: str,
    user_groups: List[str],
    is_admin: bool,
) -> bool:
    """Check if user can access a collection."""
    if is_admin:
        return True
    if collection.createdBy == username:
        return True
    if not collection.private and bool(set(user_groups) & set(collection.allowedGroups or [])):
        return True
    return False


def validate_collection_access(
    collection: RagCollectionConfig,
    username: str,
    user_groups: List[str],
    is_admin: bool,
) -> None:
    """Validate collection access and raise exception if denied."""
    if not can_access_collection(collection, username, user_groups, is_admin):
        raise ValidationError(f"Permission denied for collection {collection.collectionId}")


def can_modify_collection(
    collection: RagCollectionConfig,
    username: str,
    is_admin: bool,
) -> bool:
    """Check if user can modify a collection."""
    return is_admin or collection.createdBy == username
