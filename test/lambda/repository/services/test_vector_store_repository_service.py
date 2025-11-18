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

"""Tests for vector store repository service base class."""

import os
from unittest.mock import create_autospec, MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("RAG_DOCUMENT_TABLE", "test-doc-table")
os.environ.setdefault("RAG_SUB_DOCUMENT_TABLE", "test-subdoc-table")

from models.domain_objects import (
    CollectionStatus,
    FixedChunkingStrategy,
    IngestionJob,
    IngestionType,
    RagDocument,
    VectorStoreStatus,
)
from repository.rag_document_repo import RagDocumentRepository
from repository.services.opensearch_repository_service import OpenSearchRepositoryService


@pytest.fixture
def vector_store_repository():
    """Fixture for vector store repository configuration."""
    return {
        "repositoryId": "test-vector-repo",
        "type": "opensearch",
        "name": "Test Vector Repository",
        "endpoint": "test.opensearch.com",
        "embeddingModelId": "amazon.titan-embed-text-v1",
        "allowedGroups": ["admin"],
        "createdBy": "test-user",
        "status": VectorStoreStatus.CREATE_COMPLETE,
        "chunkingStrategy": FixedChunkingStrategy(size=512, overlap=50),
        "pipelines": [],
    }


@pytest.fixture
def vector_store_service(vector_store_repository):
    """Fixture for vector store service instance."""
    return OpenSearchRepositoryService(vector_store_repository)


@pytest.fixture
def mock_rag_document_repo():
    """Fixture for mocked RagDocumentRepository."""
    return create_autospec(RagDocumentRepository, instance=True)


@pytest.fixture
def sample_ingestion_job():
    """Fixture for sample ingestion job."""
    return IngestionJob(
        repository_id="test-vector-repo",
        collection_id="test-collection",
        s3_path="s3://test-bucket/document.pdf",
        username="test-user",
        ingestion_type=IngestionType.MANUAL,
        embedding_model="amazon.titan-embed-text-v1",
        chunk_strategy=FixedChunkingStrategy(size=512, overlap=50),
    )


class TestVectorStoreRepositoryService:
    """Test suite for VectorStoreRepositoryService base class."""

    def test_get_collection_id_from_config_with_collection_id(self, vector_store_service):
        """Test extracting collection ID when explicitly provided."""
        pipeline_config = {"collectionId": "explicit-collection"}
        collection_id = vector_store_service.get_collection_id_from_config(pipeline_config)
        assert collection_id == "explicit-collection"

    def test_get_collection_id_from_config_with_embedding_model(self, vector_store_service):
        """Test extracting collection ID from embedding model."""
        pipeline_config = {"embeddingModel": "amazon.titan-embed-text-v1"}
        collection_id = vector_store_service.get_collection_id_from_config(pipeline_config)
        assert collection_id == "amazon.titan-embed-text-v1"

    def test_ingest_document(self, vector_store_service, sample_ingestion_job, mock_rag_document_repo):
        """Test ingesting document into vector store."""
        texts = ["chunk1", "chunk2", "chunk3"]
        metadatas = [{"page": 1}, {"page": 2}, {"page": 3}]

        mock_vector_store = MagicMock()
        mock_vector_store.add_texts.return_value = ["id1", "id2", "id3"]

        mock_rag_document_repo.save.return_value = None

        with patch("repository.services.vector_store_repository_service.RagEmbeddings"):
            with patch(
                "repository.services.vector_store_repository_service.get_vector_store_client",
                return_value=mock_vector_store,
            ):
                with patch("repository.rag_document_repo.RagDocumentRepository", return_value=mock_rag_document_repo):
                    result = vector_store_service.ingest_document(sample_ingestion_job, texts, metadatas)

                    assert result.repository_id == "test-vector-repo"
                    assert result.collection_id == "test-collection"
                    assert len(result.subdocs) == 3
                    mock_vector_store.add_texts.assert_called_once()
                    mock_rag_document_repo.save.assert_called_once()

    def test_delete_document(self, vector_store_service):
        """Test deleting document from vector store."""
        document = RagDocument(
            repository_id="test-vector-repo",
            collection_id="test-collection",
            document_name="document.pdf",
            source="s3://test-bucket/document.pdf",
            subdocs=["id1", "id2", "id3"],
            chunk_strategy=FixedChunkingStrategy(size=512, overlap=50),
            username="test-user",
            ingestion_type=IngestionType.MANUAL,
        )

        mock_vector_store = MagicMock()
        mock_vector_store.delete.return_value = None

        with patch("repository.services.vector_store_repository_service.RagEmbeddings"):
            with patch(
                "repository.services.vector_store_repository_service.get_vector_store_client",
                return_value=mock_vector_store,
            ):
                vector_store_service.delete_document(document, MagicMock())

                mock_vector_store.delete.assert_called_once_with(["id1", "id2", "id3"])

    def test_retrieve_documents(self, vector_store_service):
        """Test retrieving documents from vector store."""
        mock_doc1 = MagicMock()
        mock_doc1.page_content = "Content 1"
        mock_doc1.metadata = {"source": "doc1.pdf"}

        mock_doc2 = MagicMock()
        mock_doc2.page_content = "Content 2"
        mock_doc2.metadata = {"source": "doc2.pdf"}

        mock_vector_store = MagicMock()
        mock_vector_store.similarity_search_with_score.return_value = [(mock_doc1, 0.95), (mock_doc2, 0.85)]

        with patch("repository.services.vector_store_repository_service.RagEmbeddings"):
            with patch(
                "repository.services.vector_store_repository_service.get_vector_store_client",
                return_value=mock_vector_store,
            ):
                results = vector_store_service.retrieve_documents("test query", "test-collection", 5)

                assert len(results) == 2
                assert results[0]["content"] == "Content 1"
                assert results[0]["score"] == 0.95
                assert results[1]["content"] == "Content 2"

    def test_validate_document_source_valid(self, vector_store_service):
        """Test validating valid S3 path."""
        s3_path = "s3://test-bucket/document.pdf"
        result = vector_store_service.validate_document_source(s3_path)
        assert result == s3_path

    def test_validate_document_source_invalid(self, vector_store_service):
        """Test validating invalid S3 path raises error."""
        with pytest.raises(ValueError, match="Invalid S3 path"):
            vector_store_service.validate_document_source("invalid-path")

    def test_get_vector_store_client(self, vector_store_service):
        """Test getting vector store client."""
        mock_embeddings = MagicMock()
        mock_vector_store = MagicMock()

        with patch(
            "repository.services.vector_store_repository_service.get_vector_store_client",
            return_value=mock_vector_store,
        ) as mock_get_client:
            result = vector_store_service.get_vector_store_client("test-collection", mock_embeddings)

            assert result == mock_vector_store
            mock_get_client.assert_called_once_with(
                "test-vector-repo", collection_id="test-collection", embeddings=mock_embeddings
            )

    def test_create_default_collection_active_repository(self, vector_store_service):
        """Test creating default collection for active repository."""
        collection = vector_store_service.create_default_collection()

        assert collection is not None
        assert collection.collectionId == "amazon.titan-embed-text-v1"
        assert collection.repositoryId == "test-vector-repo"
        assert collection.embeddingModel == "amazon.titan-embed-text-v1"
        assert collection.status == CollectionStatus.ACTIVE
        assert collection.default is True
        assert collection.allowChunkingOverride is True

    def test_create_default_collection_inactive_repository(self):
        """Test creating default collection for inactive repository returns None."""
        repository = {
            "repositoryId": "test-vector-repo",
            "type": "opensearch",
            "status": VectorStoreStatus.CREATE_FAILED,
            "embeddingModelId": "amazon.titan-embed-text-v1",
        }
        service = OpenSearchRepositoryService(repository)

        collection = service.create_default_collection()
        assert collection is None

    def test_create_default_collection_no_embedding_model(self):
        """Test creating default collection without embedding model returns None."""
        repository = {
            "repositoryId": "test-vector-repo",
            "type": "opensearch",
            "status": VectorStoreStatus.CREATE_COMPLETE,
        }
        service = OpenSearchRepositoryService(repository)

        collection = service.create_default_collection()
        assert collection is None

    def test_create_default_collection_exception(self, vector_store_service):
        """Test creating default collection handles exceptions."""
        with patch.object(vector_store_service, "repository", {"repositoryId": "test-vector-repo"}):
            collection = vector_store_service.create_default_collection()
            assert collection is None

    def test_store_chunks_single_batch(self, vector_store_service, sample_ingestion_job):
        """Test storing chunks in single batch."""
        texts = ["chunk1", "chunk2", "chunk3"]
        metadatas = [{"page": 1}, {"page": 2}, {"page": 3}]

        mock_vector_store = MagicMock()
        mock_vector_store.add_texts.return_value = ["id1", "id2", "id3"]

        with patch("repository.services.vector_store_repository_service.RagEmbeddings"):
            with patch(
                "repository.services.vector_store_repository_service.get_vector_store_client",
                return_value=mock_vector_store,
            ):
                result = vector_store_service._store_chunks(
                    texts, metadatas, "test-collection", "amazon.titan-embed-text-v1"
                )

                assert len(result) == 3
                assert result == ["id1", "id2", "id3"]
                mock_vector_store.add_texts.assert_called_once()

    def test_store_chunks_multiple_batches(self, vector_store_service):
        """Test storing chunks in multiple batches."""
        # Create 1000 chunks to trigger batching (batch size is 500)
        texts = [f"chunk{i}" for i in range(1000)]
        metadatas = [{"page": i} for i in range(1000)]

        mock_vector_store = MagicMock()
        mock_vector_store.add_texts.side_effect = [[f"id{i}" for i in range(500)], [f"id{i}" for i in range(500, 1000)]]

        with patch("repository.services.vector_store_repository_service.RagEmbeddings"):
            with patch(
                "repository.services.vector_store_repository_service.get_vector_store_client",
                return_value=mock_vector_store,
            ):
                result = vector_store_service._store_chunks(
                    texts, metadatas, "test-collection", "amazon.titan-embed-text-v1"
                )

                assert len(result) == 1000
                assert mock_vector_store.add_texts.call_count == 2

    def test_store_chunks_batch_failure(self, vector_store_service):
        """Test storing chunks handles batch failure."""
        texts = ["chunk1", "chunk2"]
        metadatas = [{"page": 1}, {"page": 2}]

        mock_vector_store = MagicMock()
        mock_vector_store.add_texts.return_value = None

        with patch("repository.services.vector_store_repository_service.RagEmbeddings"):
            with patch(
                "repository.services.vector_store_repository_service.get_vector_store_client",
                return_value=mock_vector_store,
            ):
                with pytest.raises(Exception, match="Failed to store batch"):
                    vector_store_service._store_chunks(
                        texts, metadatas, "test-collection", "amazon.titan-embed-text-v1"
                    )

    def test_store_chunks_no_ids_returned(self, vector_store_service):
        """Test storing chunks when no IDs are returned."""
        texts = ["chunk1"]
        metadatas = [{"page": 1}]

        mock_vector_store = MagicMock()
        mock_vector_store.add_texts.return_value = []

        with patch("repository.services.vector_store_repository_service.RagEmbeddings"):
            with patch(
                "repository.services.vector_store_repository_service.get_vector_store_client",
                return_value=mock_vector_store,
            ):
                with pytest.raises(Exception, match="Failed to store batch"):
                    vector_store_service._store_chunks(
                        texts, metadatas, "test-collection", "amazon.titan-embed-text-v1"
                    )
