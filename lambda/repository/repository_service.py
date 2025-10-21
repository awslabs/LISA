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

"""Repository service with business logic."""

import logging
from typing import Optional

from repository.vector_store_repo import VectorStoreRepository
from utilities.common_functions import user_has_group_access
from utilities.exceptions import HTTPException

logger = logging.getLogger(__name__)


class RepositoryService:
    """Service for managing repository lifecycle and business logic."""

    def __init__(
        self,
        vector_store_repo: Optional[VectorStoreRepository] = None,
    ):
        """
        Initialize the repository service.

        Args:
            vector_store_repo: Vector store repository
        """
        self.vs_repo = vector_store_repo or VectorStoreRepository()

    def get_repository(self, repository_id: str, is_admin: bool = False, user_groups: list[str] = None):
        """Ensures a user has access to the repository or else raises an HTTPException"""
        if user_groups is None:
            user_groups = []
        repo = self.vs_repo.find_repository_by_id(repository_id)
        if is_admin is False:
            if not user_has_group_access(user_groups, repo.get("allowedGroups", [])):
                raise HTTPException(status_code=403, message="User does not have permission to access this repository")
        return repo
