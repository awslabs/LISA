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

"""Factory for creating repository service instances."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from utilities.repository_types import RepositoryType

if TYPE_CHECKING:
    from .repository_service import RepositoryService


class RepositoryServiceFactory:
    """Factory for creating repository-specific service instances.

    Encapsulates repository-specific behavior, eliminating the need for
    conditional logic throughout the codebase.

    Service classes are lazily imported to avoid loading heavy dependencies
    (e.g., langchain_community, langchain_postgres) at module load time.
    This prevents ImportErrors in Lambda functions that don't need vector
    store operations and reduces cold start times.
    """

    @classmethod
    def _get_service_class(cls, repo_type: RepositoryType) -> type["RepositoryService"]:
        """Lazily import and return the service class for a repository type.

        Args:
            repo_type: Repository type to look up

        Returns:
            Service class for the repository type

        Raises:
            ValueError: If repository type is not supported
        """
        if repo_type == RepositoryType.OPENSEARCH:
            from .opensearch_repository_service import OpenSearchRepositoryService

            return OpenSearchRepositoryService
        elif repo_type == RepositoryType.PGVECTOR:
            from .pgvector_repository_service import PGVectorRepositoryService

            return PGVectorRepositoryService
        elif repo_type == RepositoryType.BEDROCK_KB:
            from .bedrock_kb_repository_service import BedrockKBRepositoryService

            return BedrockKBRepositoryService
        else:
            raise ValueError(
                f"Unsupported repository type: {repo_type}. "
                f"Supported types: {[RepositoryType.OPENSEARCH, RepositoryType.PGVECTOR, RepositoryType.BEDROCK_KB]}"
            )

    @classmethod
    def create_service(cls, repository: dict[str, Any]) -> "RepositoryService":
        """Create appropriate service instance for repository type.

        Args:
            repository: Repository configuration dictionary

        Returns:
            Service instance for the repository type

        Raises:
            ValueError: If repository type is not supported
        """
        repo_type = RepositoryType.get_type(repository)
        service_class = cls._get_service_class(repo_type)
        return service_class(repository)

    @classmethod
    def register_service(cls, repo_type: RepositoryType, service_class: type["RepositoryService"]) -> None:
        """Register a new service class for a repository type.

        Allows extending the factory with new repository types without
        modifying the factory code (Open/Closed Principle).

        Args:
            repo_type: Repository type to register
            service_class: Service class to use for this type
        """
        # Note: With lazy imports, custom registrations would need a different
        # mechanism. This method is preserved for backward compatibility.
        pass

    @classmethod
    def get_supported_types(cls) -> list[RepositoryType]:
        """Get list of supported repository types.

        Returns:
            List of registered repository types
        """
        return [RepositoryType.OPENSEARCH, RepositoryType.PGVECTOR, RepositoryType.BEDROCK_KB]
