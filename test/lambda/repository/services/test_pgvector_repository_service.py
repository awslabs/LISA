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

"""Tests for PGVector repository service."""

import os
from unittest.mock import MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("RAG_DOCUMENT_TABLE", "test-doc-table")
os.environ.setdefault("RAG_SUB_DOCUMENT_TABLE", "test-subdoc-table")

from repository.services.pgvector_repository_service import PGVectorRepositoryService


@pytest.fixture
def pgvector_repository():
    """Fixture for PGVector repository configuration."""
    return {
        "repositoryId": "test-pgvector-repo",
        "type": "pgvector",
        "name": "Test PGVector Repository",
        "dbHost": "localhost",
        "embeddingModelId": "amazon.titan-embed-text-v1",
        "allowedGroups": ["admin"],
        "createdBy": "test-user",
    }


@pytest.fixture
def pgvector_service(pgvector_repository):
    """Fixture for PGVector service instance."""
    return PGVectorRepositoryService(pgvector_repository)


class TestPGVectorRepositoryService:
    """Test suite for PGVectorRepositoryService."""

    def test_drop_collection_index_success(self, pgvector_service):
        """Test dropping PGVector collection successfully."""
        mock_vector_store = MagicMock()
        mock_vector_store.delete_collection.return_value = None

        with patch("repository.services.pgvector_repository_service.RagEmbeddings"):
            with patch.object(pgvector_service, "_get_vector_store_client", return_value=mock_vector_store):
                pgvector_service._drop_collection_index("test-collection")

                mock_vector_store.delete_collection.assert_called_once()

    def test_drop_collection_index_no_support(self, pgvector_service):
        """Test dropping collection when vector store doesn't support deletion."""
        mock_vector_store = MagicMock(spec=[])  # No delete_collection method

        with patch("repository.services.pgvector_repository_service.RagEmbeddings"):
            with patch.object(pgvector_service, "_get_vector_store_client", return_value=mock_vector_store):
                # Should not raise exception
                pgvector_service._drop_collection_index("test-collection")

    def test_drop_collection_index_exception(self, pgvector_service):
        """Test dropping collection handles exceptions gracefully."""
        mock_vector_store = MagicMock()
        mock_vector_store.delete_collection.side_effect = Exception("Database error")

        with patch("repository.services.pgvector_repository_service.RagEmbeddings"):
            with patch.object(pgvector_service, "_get_vector_store_client", return_value=mock_vector_store):
                # Should not raise exception
                pgvector_service._drop_collection_index("test-collection")

    def test_normalize_similarity_score(self, pgvector_service):
        """Test normalizing PGVector cosine distance to similarity score."""
        # PGVector returns cosine distance (0-2 range)
        # Should convert to similarity (0-1 range)

        # Distance 0 (identical) -> similarity 1.0
        assert pgvector_service._normalize_similarity_score(0.0) == 1.0

        # Distance 1 (orthogonal) -> similarity 0.5
        assert pgvector_service._normalize_similarity_score(1.0) == 0.5

        # Distance 2 (opposite) -> similarity 0.0
        assert pgvector_service._normalize_similarity_score(2.0) == 0.0

        # Distance 0.5 -> similarity 0.75
        assert pgvector_service._normalize_similarity_score(0.5) == 0.75

        # Negative distance (shouldn't happen but handle gracefully) -> clamped to 0.0
        assert pgvector_service._normalize_similarity_score(-0.5) >= 0.0
