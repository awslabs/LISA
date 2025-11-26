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

from typing import Any, Dict, Type

from utilities.repository_types import RepositoryType

from .bedrock_kb_repository_service import BedrockKBRepositoryService
from .opensearch_repository_service import OpenSearchRepositoryService
from .pgvector_repository_service import PGVectorRepositoryService
from .repository_service import RepositoryService


class RepositoryServiceFactory:
    """Factory for creating repository-specific service instances.

    Encapsulates repository-specific behavior, eliminating the need for
    conditional logic throughout the codebase.
    """

    # Registry mapping repository types to service classes
    _services: Dict[RepositoryType, Type[RepositoryService]] = {
        RepositoryType.OPENSEARCH: OpenSearchRepositoryService,
        RepositoryType.PGVECTOR: PGVectorRepositoryService,
        RepositoryType.BEDROCK_KB: BedrockKBRepositoryService,
    }

    @classmethod
    def create_service(cls, repository: Dict[str, Any]) -> RepositoryService:
        """Create appropriate service instance for repository type.

        Args:
            repository: Repository configuration dictionary

        Returns:
            Service instance for the repository type

        Raises:
            ValueError: If repository type is not supported
        """
        repo_type = RepositoryType.get_type(repository)

        service_class = cls._services.get(repo_type)
        if not service_class:
            raise ValueError(
                f"Unsupported repository type: {repo_type}. " f"Supported types: {list(cls._services.keys())}"
            )

        return service_class(repository)

    @classmethod
    def register_service(cls, repo_type: RepositoryType, service_class: Type[RepositoryService]) -> None:
        """Register a new service class for a repository type.

        Allows extending the factory with new repository types without
        modifying the factory code (Open/Closed Principle).

        Args:
            repo_type: Repository type to register
            service_class: Service class to use for this type
        """
        cls._services[repo_type] = service_class

    @classmethod
    def get_supported_types(cls) -> list[RepositoryType]:
        """Get list of supported repository types.

        Returns:
            List of registered repository types
        """
        return list(cls._services.keys())
