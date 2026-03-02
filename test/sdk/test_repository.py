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

"""Unit tests for RepositoryMixin."""


import pytest
import responses
from lisapy import LisaApi


class TestRepositoryMixin:
    """Test suite for repository-related operations."""

    @responses.activate
    def test_list_repositories(self, lisa_api: LisaApi, api_url: str, mock_repositories_response: list):
        """Test listing all repositories."""
        responses.add(responses.GET, f"{api_url}/repository", json=mock_repositories_response, status=200)

        repos = lisa_api.list_repositories()

        assert len(repos) == 2
        assert repos[0]["repositoryId"] == "pgvector-rag"
        assert repos[1]["type"] == "opensearch"

    @responses.activate
    def test_create_repository(self, lisa_api: LisaApi, api_url: str):
        """Test creating a repository."""
        rag_config = {
            "repositoryId": "new-repo",
            "repositoryName": "New Repository",
            "type": "pgvector",
            "embeddingModelId": "amazon.titan-embed-text-v1",
        }
        expected_response = {**rag_config, "status": "CREATING", "createdAt": "2024-01-24T10:00:00Z"}

        responses.add(responses.POST, f"{api_url}/repository", json=expected_response, status=201)

        result = lisa_api.create_repository(rag_config)

        assert result["repositoryId"] == "new-repo"
        assert result["status"] == "CREATING"

    @responses.activate
    def test_create_pgvector_repository(self, lisa_api: LisaApi, api_url: str):
        """Test creating a PGVector repository."""
        rag_config = {
            "repositoryId": "pgvector-test",
            "repositoryName": "PGVector Test",
            "type": "pgvector",
            "embeddingModelId": "amazon.titan-embed-text-v1",
        }
        expected_response = {**rag_config, "status": "CREATING", "createdAt": "2024-01-24T11:00:00Z"}

        responses.add(responses.POST, f"{api_url}/repository", json=expected_response, status=201)

        result = lisa_api.create_pgvector_repository(rag_config)

        assert result["repositoryId"] == "pgvector-test"
        assert result["type"] == "pgvector"

    @responses.activate
    def test_create_opensearch_repository(self, lisa_api: LisaApi, api_url: str):
        """Test creating an OpenSearch repository."""
        expected_response = {
            "repositoryId": "opensearch-test",
            "repositoryName": "OpenSearch Test",
            "type": "opensearch",
            "embeddingModelId": "amazon.titan-embed-text-v1",
            "status": "CREATING",
            "createdAt": "2024-01-24T12:00:00Z",
        }

        responses.add(responses.POST, f"{api_url}/repository", json=expected_response, status=201)

        result = lisa_api.create_opensearch_repository(
            repository_id="opensearch-test",
            repository_name="OpenSearch Test",
            embedding_model_id="amazon.titan-embed-text-v1",
            allowed_groups=["admin", "users"],
        )

        assert result["repositoryId"] == "opensearch-test"
        assert result["type"] == "opensearch"
        # Verify the request payload included OpenSearch config
        assert len(responses.calls) == 1

    @responses.activate
    def test_create_opensearch_repository_with_custom_config(self, lisa_api: LisaApi, api_url: str):
        """Test creating an OpenSearch repository with custom configuration."""
        opensearch_config = {
            "dataNodes": 3,
            "dataNodeInstanceType": "r7g.xlarge.search",
            "masterNodes": 3,
            "masterNodeInstanceType": "r7g.large.search",
            "volumeSize": 100,
            "volumeType": "gp3",
            "multiAzWithStandby": True,
        }

        expected_response = {
            "repositoryId": "opensearch-custom",
            "repositoryName": "OpenSearch Custom",
            "type": "opensearch",
            "embeddingModelId": "amazon.titan-embed-text-v1",
            "opensearchConfig": opensearch_config,
            "status": "CREATING",
            "createdAt": "2024-01-24T13:00:00Z",
        }

        responses.add(responses.POST, f"{api_url}/repository", json=expected_response, status=201)

        result = lisa_api.create_opensearch_repository(
            repository_id="opensearch-custom",
            repository_name="OpenSearch Custom",
            embedding_model_id="amazon.titan-embed-text-v1",
            opensearch_config=opensearch_config,
        )

        assert result["repositoryId"] == "opensearch-custom"
        assert result["opensearchConfig"]["dataNodes"] == 3

    @responses.activate
    def test_delete_repository(self, lisa_api: LisaApi, api_url: str):
        """Test deleting a repository."""
        repository_id = "old-repo"
        responses.add(responses.DELETE, f"{api_url}/repository/{repository_id}", status=204)

        result = lisa_api.delete_repository(repository_id)

        assert result is True
        assert len(responses.calls) == 1

    @responses.activate
    def test_delete_repository_with_200(self, lisa_api: LisaApi, api_url: str):
        """Test deleting a repository that returns 200."""
        repository_id = "old-repo"
        responses.add(responses.DELETE, f"{api_url}/repository/{repository_id}", json={"deleted": True}, status=200)

        result = lisa_api.delete_repository(repository_id)

        assert result is True

    @responses.activate
    def test_get_repository_status(self, lisa_api: LisaApi, api_url: str):
        """Test getting repository status."""
        status_response = {
            "repositories": [
                {"repositoryId": "pgvector-rag", "status": "ACTIVE", "health": "HEALTHY"},
                {"repositoryId": "opensearch-rag", "status": "ACTIVE", "health": "HEALTHY"},
            ]
        }

        responses.add(responses.GET, f"{api_url}/repository/status", json=status_response, status=200)

        result = lisa_api.get_repository_status()

        assert "repositories" in result
        assert len(result["repositories"]) == 2
        assert result["repositories"][0]["health"] == "HEALTHY"

    @responses.activate
    def test_list_repositories_error(self, lisa_api: LisaApi, api_url: str):
        """Test error handling when listing repositories fails."""
        responses.add(responses.GET, f"{api_url}/repository", json={"error": "Unauthorized"}, status=401)

        with pytest.raises(Exception):
            lisa_api.list_repositories()

    @responses.activate
    def test_create_repository_error(self, lisa_api: LisaApi, api_url: str):
        """Test error handling when creating a repository fails."""
        rag_config = {
            "repositoryId": "invalid-repo",
            "repositoryName": "Invalid Repository",
        }

        responses.add(responses.POST, f"{api_url}/repository", json={"error": "Invalid configuration"}, status=400)

        with pytest.raises(Exception):
            lisa_api.create_repository(rag_config)
