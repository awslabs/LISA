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

"""Tests for OpenSearch repository service."""

import os
from unittest.mock import MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("RAG_DOCUMENT_TABLE", "test-doc-table")
os.environ.setdefault("RAG_SUB_DOCUMENT_TABLE", "test-subdoc-table")

from repository.services.opensearch_repository_service import OpenSearchRepositoryService


@pytest.fixture
def opensearch_repository():
    """Fixture for OpenSearch repository configuration."""
    return {
        "repositoryId": "test-opensearch-repo",
        "type": "opensearch",
        "name": "Test OpenSearch Repository",
        "endpoint": "test.opensearch.com",
        "embeddingModelId": "amazon.titan-embed-text-v1",
        "allowedGroups": ["admin"],
        "createdBy": "test-user",
    }


@pytest.fixture
def opensearch_service(opensearch_repository):
    """Fixture for OpenSearch service instance."""
    return OpenSearchRepositoryService(opensearch_repository)


class TestOpenSearchRepositoryService:
    """Test suite for OpenSearchRepositoryService."""

    def test_drop_collection_index_success(self, opensearch_service):
        """Test dropping OpenSearch index successfully."""
        mock_vector_store = MagicMock()
        mock_vector_store.client.indices.exists.return_value = True
        mock_vector_store.client.indices.delete.return_value = {"acknowledged": True}

        with patch("repository.services.opensearch_repository_service.RagEmbeddings"):
            with patch(
                "repository.services.opensearch_repository_service.get_vector_store_client",
                return_value=mock_vector_store,
            ):
                opensearch_service._drop_collection_index("test-collection")

                mock_vector_store.client.indices.exists.assert_called_once()
                mock_vector_store.client.indices.delete.assert_called_once()

    def test_drop_collection_index_not_exists(self, opensearch_service):
        """Test dropping OpenSearch index that doesn't exist."""
        mock_vector_store = MagicMock()
        mock_vector_store.client.indices.exists.return_value = False

        with patch("repository.services.opensearch_repository_service.RagEmbeddings"):
            with patch(
                "repository.services.opensearch_repository_service.get_vector_store_client",
                return_value=mock_vector_store,
            ):
                opensearch_service._drop_collection_index("test-collection")

                mock_vector_store.client.indices.exists.assert_called_once()
                mock_vector_store.client.indices.delete.assert_not_called()

    def test_drop_collection_index_no_client_support(self, opensearch_service):
        """Test dropping index when vector store doesn't support index operations."""
        mock_vector_store = MagicMock(spec=[])  # No client attribute

        with patch("repository.services.opensearch_repository_service.RagEmbeddings"):
            with patch(
                "repository.services.opensearch_repository_service.get_vector_store_client",
                return_value=mock_vector_store,
            ):
                # Should not raise exception
                opensearch_service._drop_collection_index("test-collection")

    def test_drop_collection_index_exception(self, opensearch_service):
        """Test dropping index handles exceptions gracefully."""
        mock_vector_store = MagicMock()
        mock_vector_store.client.indices.exists.side_effect = Exception("Connection error")

        with patch("repository.services.opensearch_repository_service.RagEmbeddings"):
            with patch(
                "repository.services.opensearch_repository_service.get_vector_store_client",
                return_value=mock_vector_store,
            ):
                # Should not raise exception
                opensearch_service._drop_collection_index("test-collection")
