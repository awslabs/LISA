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
from utilities.common_functions import api_wrapper, get_groups, get_id_token, retry_config, user_has_group_access
from utilities.exceptions import HTTPException


logger = logging.getLogger(__name__)


class RepositoryService:
    """Service for managing repository lifecycle and business logic."""

    def __init__(
        self,
        vector_store_repo: Optional[VectorStoreRepository] = None,
    ):
        """
        Initialize the collection management service.

        Args:
            vector_store_repo: Vector store repository
            validation_service: Validation service
            access_control_service: Access control service
        """
        self.collection_repo = collection_repo or CollectionRepository()
        self.document_repo = document_repo
        self.vs_repo = vector_store_repo or VectorStoreRepository()
        self.validation_service = validation_service or CollectionValidationService(
            self.collection_repo, self.vector_store_repo
        )
        self.access_control_service = access_control_service or CollectionAccessControlService(
            self.collection_repo, self.vector_store_repo
        )

    def get_repository(self, event: dict[str, Any], repository_id: str, is_admin: bool = false, user_groups: list[str] = []) -> None:
        repo = self.vs_repo.find_repository_by_id(repository_id)
        """Ensures a user has access to the repository or else raises an HTTPException"""
        if is_admin is False:
            if not user_has_group_access(user_groups, repo.get("allowedGroups", [])):
                raise HTTPException(status_code=403, message="User does not have permission to access this repository")
        return repo

