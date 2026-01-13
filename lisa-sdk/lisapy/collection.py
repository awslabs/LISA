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

"""Collection management operations for LISA SDK."""

from typing import Dict, List, Optional

from .common import BaseMixin
from .errors import parse_error


class CollectionMixin(BaseMixin):
    """Mixin for collection-related operations."""

    def create_collection(
        self,
        repository_id: str,
        name: str,
        description: Optional[str] = None,
        embedding_model: Optional[str] = None,
        chunking_strategy: Optional[Dict] = None,
        allowed_groups: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
        allow_chunking_override: bool = False,
    ) -> Dict:
        """Create a new collection in a repository.

        Args:
            repository_id: The repository ID to create the collection in
            name: Name of the collection (required)
            description: Optional description of the collection
            embedding_model: Optional embedding model ID (inherits from repository if not provided)
            chunking_strategy: Optional chunking strategy configuration
            allowed_groups: Optional list of groups allowed to access the collection
            metadata: Optional metadata tags for the collection
            allow_chunking_override: Whether to allow chunking strategy override (default: False)

        Returns:
            Dict: Created collection configuration

        Raises:
            Exception: If the request fails
        """
        payload = {
            "name": name,
            "description": description,
            "embeddingModel": embedding_model,
            "chunkingStrategy": chunking_strategy,
            "allowedGroups": allowed_groups,
            "metadata": metadata,
            "allowChunkingOverride": allow_chunking_override,
        }

        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}

        response = self._session.post(f"{self.url}/repository/{repository_id}/collection", json=payload)
        if response.status_code in [200, 201]:
            return response.json()  # type: ignore[no-any-return]
        else:
            raise parse_error(response.status_code, response)

    def get_collection(self, repository_id: str, collection_id: str) -> Dict:
        """Get a collection by ID.

        Args:
            repository_id: The repository ID
            collection_id: The collection ID

        Returns:
            Dict: Collection configuration

        Raises:
            Exception: If the request fails
        """
        response = self._session.get(f"{self.url}/repository/{repository_id}/collection/{collection_id}")
        if response.status_code == 200:
            return response.json()  # type: ignore[no-any-return]
        else:
            raise parse_error(response.status_code, response)

    def update_collection(
        self,
        repository_id: str,
        collection_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        chunking_strategy: Optional[Dict] = None,
        allowed_groups: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
        allow_chunking_override: Optional[bool] = None,
        status: Optional[str] = None,
    ) -> Dict:
        """Update a collection.

        Args:
            repository_id: The repository ID
            collection_id: The collection ID
            name: Optional new name
            description: Optional new description
            chunking_strategy: Optional new chunking strategy
            allowed_groups: Optional new allowed groups list
            metadata: Optional new metadata
            allow_chunking_override: Optional new allow_chunking_override setting
            status: Optional new status

        Returns:
            Dict: Updated collection configuration

        Raises:
            Exception: If the request fails
        """
        payload = {
            "name": name,
            "description": description,
            "chunkingStrategy": chunking_strategy,
            "allowedGroups": allowed_groups,
            "metadata": metadata,
            "allowChunkingOverride": allow_chunking_override,
            "status": status,
        }

        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}

        response = self._session.put(f"{self.url}/repository/{repository_id}/collection/{collection_id}", json=payload)
        if response.status_code == 200:
            return response.json()  # type: ignore[no-any-return]
        else:
            raise parse_error(response.status_code, response)

    def delete_collection(self, repository_id: str, collection_id: str) -> bool:
        """Delete a collection.

        Args:
            repository_id: The repository ID
            collection_id: The collection ID

        Returns:
            bool: True if deletion was successful

        Raises:
            Exception: If the request fails
        """
        response = self._session.delete(f"{self.url}/repository/{repository_id}/collection/{collection_id}")
        if response.status_code in [200, 204]:
            return True
        else:
            raise parse_error(response.status_code, response)

    def list_collections(
        self,
        repository_id: str,
        page: int = 1,
        page_size: int = 20,
        filter_text: Optional[str] = None,
        status_filter: Optional[str] = None,
        sort_by: str = "createdAt",
        sort_order: str = "desc",
    ) -> Dict:
        """List collections in a repository.

        Args:
            repository_id: The repository ID
            page: Page number (default: 1)
            page_size: Number of items per page (default: 20, max: 100)
            filter_text: Optional text filter for name/description
            status_filter: Optional status filter (active, archived, deleted)
            sort_by: Field to sort by (name, createdAt, updatedAt)
            sort_order: Sort order (asc, desc)

        Returns:
            Dict: Paginated list of collections with metadata

        Raises:
            Exception: If the request fails
        """
        params: dict[str, str | int] = {
            "page": page,
            "pageSize": min(page_size, 100),
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }

        if filter_text:
            params["filterText"] = filter_text
        if status_filter:
            params["statusFilter"] = status_filter

        response = self._session.get(f"{self.url}/repository/{repository_id}/collections", params=params)
        if response.status_code == 200:
            return response.json()  # type: ignore[no-any-return]
        else:
            raise parse_error(response.status_code, response)

    def get_user_collections(
        self,
        page_size: int = 20,
        filter_text: Optional[str] = None,
        sort_by: str = "createdAt",
        sort_order: str = "desc",
        last_evaluated_key: Optional[str] = None,
    ) -> List[Dict]:
        """Get all collections user has access to across all repositories.

        Args:
            page_size: Number of items per page (default: 20, max: 100)
            filter_text: Optional text filter for name/description
            sort_by: Field to sort by (name, createdAt, updatedAt)
            sort_order: Sort order (asc, desc)
            last_evaluated_key: Optional pagination token

        Returns:
            List[Dict]: List of collections user has access to

        Raises:
            Exception: If the request fails
        """
        params: dict[str, str | int] = {
            "pageSize": min(page_size, 100),
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }

        if filter_text:
            params["filter"] = filter_text
        if last_evaluated_key:
            params["lastEvaluatedKey"] = last_evaluated_key

        response = self._session.get(f"{self.url}/repository/collections", params=params)
        if response.status_code == 200:
            result = response.json()
            return result.get("collections", [])  # type: ignore[no-any-return]
        else:
            raise parse_error(response.status_code, response)
