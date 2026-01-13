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

from typing import Dict, List

from .common import BaseMixin
from .errors import parse_error
from .types import RagRepositoryConfig


class RepositoryMixin(BaseMixin):
    """Mixin for repository-related operations."""

    def list_repositories(self) -> List[Dict]:
        """List all available repositories.

        Returns:
            List[Dict]: List of repository configurations

        Raises:
            Exception: If the request fails
        """
        response = self._session.get(f"{self.url}/repository")
        if response.status_code == 200:
            json_models: List[Dict] = response.json()
            return json_models
        else:
            raise parse_error(response.status_code, response)

    def create_repository(self, rag_config: RagRepositoryConfig) -> Dict:
        """Create a new RAG repository.

        Args:
            rag_config: Configuration for the RAG repository

        Returns:
            Dict: Created repository information

        Raises:
            Exception: If the request fails
        """
        response = self._session.post(f"{self.url}/repository", json=rag_config)
        if response.status_code in [200, 201]:
            return response.json()  # type: ignore[no-any-return]
        else:
            raise parse_error(response.status_code, response)

    def create_pgvector_repository(self, rag_config: Dict) -> Dict:
        """Create a PGVector repository configuration.

        Args:
            rag_config: RAG configuration for the PGVector repository (will be wrapped in ragConfig)

        Returns:
            Dict: Created repository information
        """
        return self.create_repository(rag_config)  # type: ignore[arg-type]

    def create_opensearch_repository(
        self,
        repository_id: str,
        repository_name: str | None = None,
        embedding_model_id: str | None = None,
        opensearch_config: Dict | None = None,
        allowed_groups: List[str] | None = None,
    ) -> Dict:
        """Create an OpenSearch repository configuration.

        Args:
            repository_id: Unique identifier for the repository
            repository_name: User-friendly name for the repository
            embedding_model_id: Default embedding model ID
            opensearch_config: OpenSearch configuration (optional - will create new cluster if not provided)
            allowed_groups: List of groups allowed access

        Returns:
            Dict: Created repository information
        """
        rag_config = {
            "repositoryId": repository_id,
            "repositoryName": repository_name or repository_id,
            "type": "opensearch",
            "embeddingModelId": embedding_model_id,
            "allowedGroups": allowed_groups or [],
        }

        if opensearch_config:
            rag_config["opensearchConfig"] = opensearch_config
        else:
            # Create new OpenSearch cluster config
            rag_config["opensearchConfig"] = {
                "dataNodes": 2,
                "dataNodeInstanceType": "r7g.large.search",
                "masterNodes": 0,
                "masterNodeInstanceType": "r7g.large.search",
                "volumeSize": 20,
                "volumeType": "gp3",
                "multiAzWithStandby": False,
            }

        return self.create_repository(rag_config)  # type: ignore[arg-type]

    def create_bedrock_kb_repository(self, rag_config: Dict) -> Dict:
        """Create a Bedrock Knowledge Base repository configuration.

        Args:
            rag_config: RAG configuration for the Bedrock KB repository

        Returns:
            Dict: Created repository information
        """
        return self.create_repository(rag_config)

    def delete_repository(self, repository_id: str) -> bool:
        """Delete a repository.

        Args:
            repository_id: The ID of the repository to delete

        Returns:
            bool: True if deletion was successful

        Raises:
            Exception: If the request fails
        """
        response = self._session.delete(f"{self.url}/repository/{repository_id}")
        if response.status_code in [200, 204]:
            return True
        else:
            raise parse_error(response.status_code, response)

    def get_repository_status(self) -> Dict:
        """Get the status of RAG repositories.

        Returns:
            Dict: Repository status information

        Raises:
            Exception: If the request fails
        """
        response = self._session.get(f"{self.url}/repository/status")
        if response.status_code == 200:
            return response.json()
        else:
            raise parse_error(response.status_code, response)
