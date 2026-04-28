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

"""Tests for Bedrock KB repository service."""

import os
from unittest.mock import create_autospec, MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("RAG_DOCUMENT_TABLE", "test-doc-table")
os.environ.setdefault("RAG_SUB_DOCUMENT_TABLE", "test-subdoc-table")

from botocore.exceptions import ClientError
from models.domain_objects import CollectionStatus, IngestionJob, IngestionType, NoneChunkingStrategy, RagDocument
from repository.rag_document_repo import RagDocumentRepository
from repository.services.bedrock_kb_repository_service import BedrockKBRepositoryService
from utilities.exceptions import ServiceUnavailableException


@pytest.fixture
def bedrock_kb_repository():
    """Fixture for Bedrock KB repository configuration."""
    return {
        "repositoryId": "test-kb-repo",
        "type": "bedrock_knowledge_base",
        "name": "Test KB Repository",
        "embeddingModelId": "amazon.titan-embed-text-v1",
        "allowedGroups": ["admin"],
        "createdBy": "test-user",
        "bedrockKnowledgeBaseConfig": {
            "bedrockKnowledgeBaseId": "kb-123",
            "bedrockKnowledgeDatasourceId": "ds-456",
            "bedrockKnowledgeDatasourceS3Bucket": "test-kb-bucket",
        },
    }


@pytest.fixture
def bedrock_kb_service(bedrock_kb_repository):
    """Fixture for Bedrock KB service instance."""
    return BedrockKBRepositoryService(bedrock_kb_repository)


@pytest.fixture
def mock_rag_document_repo():
    """Fixture for mocked RagDocumentRepository."""
    return create_autospec(RagDocumentRepository, instance=True)


@pytest.fixture
def sample_ingestion_job():
    """Fixture for sample ingestion job."""
    return IngestionJob(
        repository_id="test-kb-repo",
        collection_id="ds-456",
        s3_path="s3://test-kb-bucket/document.pdf",
        username="test-user",
        ingestion_type=IngestionType.MANUAL,
    )


class TestBedrockKBRepositoryService:
    """Test suite for BedrockKBRepositoryService."""

    def test_get_collection_id_from_config(self, bedrock_kb_service):
        """Test extracting collection ID from config."""
        pipeline_config = {}
        collection_id = bedrock_kb_service.get_collection_id_from_config(pipeline_config)
        assert collection_id == "ds-456"

    def test_get_collection_id_missing_data_source(self):
        """Test error when data source ID is missing."""
        repository = {
            "repositoryId": "test-kb-repo",
            "type": "bedrock_knowledge_base",
            "bedrockKnowledgeBaseConfig": {},
        }
        service = BedrockKBRepositoryService(repository)

        with pytest.raises(ValueError, match="missing data source ID"):
            service.get_collection_id_from_config({})

    def test_ingest_document_new(self, bedrock_kb_service, sample_ingestion_job, mock_rag_document_repo):
        """Test ingesting a new document."""
        mock_rag_document_repo.find_by_source.return_value = iter([])
        mock_rag_document_repo.save.return_value = None

        with patch(
            "repository.services.bedrock_kb_repository_service.RagDocumentRepository",
            return_value=mock_rag_document_repo,
        ):
            result = bedrock_kb_service.ingest_document(sample_ingestion_job, [], [])

            assert result.repository_id == "test-kb-repo"
            assert result.collection_id == "ds-456"
            assert result.source == "s3://test-kb-bucket/document.pdf"
            assert isinstance(result.chunk_strategy, NoneChunkingStrategy)
            mock_rag_document_repo.save.assert_called_once()

    def test_ingest_document_existing(self, bedrock_kb_service, sample_ingestion_job, mock_rag_document_repo):
        """Test ingesting an existing document updates timestamp."""
        existing_doc = RagDocument(
            repository_id="test-kb-repo",
            collection_id="ds-456",
            document_name="document.pdf",
            source="s3://test-kb-bucket/document.pdf",
            subdocs=[],
            chunk_strategy=NoneChunkingStrategy(),
            username="test-user",
            ingestion_type=IngestionType.MANUAL,
        )
        original_timestamp = existing_doc.upload_date
        mock_rag_document_repo.find_by_source.return_value = iter([existing_doc])
        mock_rag_document_repo.save.return_value = None

        with patch(
            "repository.services.bedrock_kb_repository_service.RagDocumentRepository",
            return_value=mock_rag_document_repo,
        ):
            result = bedrock_kb_service.ingest_document(sample_ingestion_job, [], [])

            assert result.document_id == existing_doc.document_id
            assert result.upload_date >= original_timestamp
            mock_rag_document_repo.save.assert_called_once()

    def test_delete_document(self, bedrock_kb_service):
        """Test deleting a document."""
        document = RagDocument(
            repository_id="test-kb-repo",
            collection_id="ds-456",
            document_name="document.pdf",
            source="s3://test-kb-bucket/document.pdf",
            subdocs=[],
            chunk_strategy=NoneChunkingStrategy(),
            username="test-user",
            ingestion_type=IngestionType.MANUAL,
        )

        mock_s3_client = MagicMock()
        mock_bedrock_agent_client = MagicMock()

        with patch("repository.services.bedrock_kb_repository_service.delete_document_from_kb") as mock_delete:
            bedrock_kb_service.delete_document(document, mock_s3_client, mock_bedrock_agent_client)
            mock_delete.assert_called_once()

    def test_delete_document_missing_bedrock_client(self, bedrock_kb_service):
        """Test deleting document without Bedrock client raises error."""
        document = RagDocument(
            repository_id="test-kb-repo",
            collection_id="ds-456",
            document_name="document.pdf",
            source="s3://test-kb-bucket/document.pdf",
            subdocs=[],
            chunk_strategy=NoneChunkingStrategy(),
            username="test-user",
            ingestion_type=IngestionType.MANUAL,
        )

        with pytest.raises(ValueError, match="Bedrock agent client required"):
            bedrock_kb_service.delete_document(document, MagicMock(), None)

    def test_delete_collection(self, bedrock_kb_service):
        """Test deleting a collection."""
        mock_s3_client = MagicMock()
        mock_bedrock_agent_client = MagicMock()

        mock_table = MagicMock()
        mock_table.query.return_value = {
            "Items": [
                {"pk": "test-kb-repo#ds-456", "source": "s3://test-kb-bucket/doc1.pdf", "ingestion_type": "manual"},
                {"pk": "test-kb-repo#ds-456", "source": "s3://test-kb-bucket/doc2.pdf", "ingestion_type": "auto"},
                {"pk": "test-kb-repo#ds-456", "source": "s3://test-kb-bucket/doc3.pdf", "ingestion_type": "existing"},
            ]
        }

        mock_dynamodb = MagicMock()
        mock_dynamodb.Table.return_value = mock_table

        with patch("boto3.resource", return_value=mock_dynamodb):
            with patch(
                "repository.services.bedrock_kb_repository_service.bulk_delete_documents_from_kb"
            ) as mock_bulk_delete:
                bedrock_kb_service.delete_collection("ds-456", mock_s3_client, mock_bedrock_agent_client)

                # Should only delete LISA-managed documents (manual and auto)
                call_args = mock_bulk_delete.call_args
                s3_paths = call_args[1]["s3_paths"]
                assert len(s3_paths) == 2
                assert "s3://test-kb-bucket/doc1.pdf" in s3_paths
                assert "s3://test-kb-bucket/doc2.pdf" in s3_paths

    def test_delete_collection_missing_bedrock_client(self, bedrock_kb_service):
        """Test deleting collection without Bedrock client raises error."""
        with pytest.raises(ValueError, match="Bedrock agent client required"):
            bedrock_kb_service.delete_collection("ds-456", MagicMock(), None)

    def test_retrieve_documents(self, bedrock_kb_service):
        """Test retrieving documents from Bedrock KB."""
        mock_bedrock_agent_client = MagicMock()
        mock_bedrock_agent_client.retrieve.return_value = {
            "retrievalResults": [
                {
                    "content": {"text": "Test content 1"},
                    "metadata": {"source": "doc1.pdf"},
                    "score": 0.95,
                    "location": {"s3Location": {"uri": "s3://bucket/doc1.pdf"}},
                },
                {
                    "content": {"text": "Test content 2"},
                    "metadata": {"source": "doc2.pdf"},
                    "score": 0.85,
                    "location": {"s3Location": {"uri": "s3://bucket/doc2.pdf"}},
                },
            ]
        }

        results = bedrock_kb_service.retrieve_documents(
            "test query", "ds-456", 5, "test-model", bedrock_agent_client=mock_bedrock_agent_client
        )

        assert len(results) == 2
        assert results[0]["page_content"] == "Test content 1"
        assert results[1]["page_content"] == "Test content 2"

    def test_retrieve_documents_missing_bedrock_client(self, bedrock_kb_service):
        """Test retrieving documents without Bedrock client raises error."""
        with pytest.raises(ValueError, match="Bedrock agent client required"):
            bedrock_kb_service.retrieve_documents("query", "ds-456", 5, "test-model", None)

    def test_retrieve_documents_missing_kb_id(self):
        """Test retrieving documents with missing KB ID raises error."""
        repository = {
            "repositoryId": "test-kb-repo",
            "type": "bedrock_knowledge_base",
            "bedrockKnowledgeBaseConfig": {"bedrockKnowledgeDatasourceId": "ds-456"},
        }
        service = BedrockKBRepositoryService(repository)

        with pytest.raises(ValueError, match="missing required field"):
            service.retrieve_documents("query", "ds-456", 5, "test-model", bedrock_agent_client=MagicMock())

    def test_validate_document_source_valid(self, bedrock_kb_service):
        """Test validating document from correct bucket."""
        s3_path = "s3://test-kb-bucket/document.pdf"
        result = bedrock_kb_service.validate_document_source(s3_path)
        assert result == s3_path

    def test_validate_document_source_wrong_bucket(self, bedrock_kb_service):
        """Test validating document from wrong bucket normalizes path."""
        s3_path = "s3://wrong-bucket/document.pdf"
        result = bedrock_kb_service.validate_document_source(s3_path)
        assert result == "s3://test-kb-bucket/document.pdf"

    def test_get_vector_store_client(self, bedrock_kb_service):
        """Test that Bedrock KB returns None for vector store client."""
        result = bedrock_kb_service.get_vector_store_client("ds-456", MagicMock())
        assert result is None

    def test_create_default_collection(self, bedrock_kb_service):
        """Test creating default collection for Bedrock KB."""
        collection = bedrock_kb_service.create_default_collection()

        assert collection is not None
        assert collection.collectionId == "ds-456"
        assert collection.repositoryId == "test-kb-repo"
        assert collection.embeddingModel == "amazon.titan-embed-text-v1"
        assert collection.status == CollectionStatus.ACTIVE
        assert collection.default is True
        assert collection.allowChunkingOverride is False
        assert collection.dataSourceId == "ds-456"

    def test_create_default_collection_missing_data_source(self):
        """Test creating default collection with missing data source returns None."""
        repository = {
            "repositoryId": "test-kb-repo",
            "type": "bedrock_knowledge_base",
            "bedrockKnowledgeBaseConfig": {},
        }
        service = BedrockKBRepositoryService(repository)

        collection = service.create_default_collection()
        assert collection is None

    def test_create_default_collection_exception(self, bedrock_kb_service):
        """Test creating default collection handles exceptions."""
        with patch.object(bedrock_kb_service, "repository", {"repositoryId": "test-kb-repo"}):
            collection = bedrock_kb_service.create_default_collection()
            assert collection is None

    def test_supports_hybrid_search(self, bedrock_kb_service):
        """Bedrock KB supports hybrid search."""
        assert bedrock_kb_service.supports_hybrid_search() is True

    def test_hybrid_retrieve_sends_hybrid_search_type(self, bedrock_kb_service):
        """hybrid_retrieve sends overrideSearchType HYBRID to Bedrock API."""
        mock_client = MagicMock()
        mock_client.retrieve.return_value = {"retrievalResults": []}

        bedrock_kb_service.hybrid_retrieve(
            query="test",
            collection_id="ds-456",
            top_k=5,
            model_name="test-model",
            bedrock_agent_client=mock_client,
        )

        call_args = mock_client.retrieve.call_args[1]
        vector_config = call_args["retrievalConfiguration"]["vectorSearchConfiguration"]
        assert vector_config["overrideSearchType"] == "HYBRID"

    def test_hybrid_retrieve_applies_data_source_filter(self, bedrock_kb_service):
        """hybrid_retrieve applies data source filter same as retrieve_documents."""
        mock_client = MagicMock()
        mock_client.retrieve.return_value = {"retrievalResults": []}

        bedrock_kb_service.hybrid_retrieve(
            query="test",
            collection_id="ds-456",
            top_k=5,
            model_name="m",
            bedrock_agent_client=mock_client,
        )

        call_args = mock_client.retrieve.call_args[1]
        vector_config = call_args["retrievalConfiguration"]["vectorSearchConfiguration"]
        assert vector_config["filter"]["equals"]["key"] == "x-amz-bedrock-kb-data-source-id"
        assert vector_config["filter"]["equals"]["value"] == "ds-456"

    def test_hybrid_retrieve_returns_documents_with_hybrid_metadata(self, bedrock_kb_service):
        """hybrid_retrieve includes retrieval_method, actual_mode_used, hybrid_supported in metadata."""
        mock_client = MagicMock()
        mock_client.retrieve.return_value = {
            "retrievalResults": [
                {
                    "content": {"text": "Hybrid result"},
                    "metadata": {},
                    "score": 0.92,
                    "location": {"s3Location": {"uri": "s3://bucket/doc.pdf"}},
                }
            ]
        }

        results = bedrock_kb_service.hybrid_retrieve(
            query="test",
            collection_id="ds-456",
            top_k=5,
            model_name="m",
            include_score=True,
            bedrock_agent_client=mock_client,
        )

        assert len(results) == 1
        assert results[0]["page_content"] == "Hybrid result"
        meta = results[0]["metadata"]
        assert meta["retrieval_method"] == "hybrid"
        assert meta["actual_mode_used"] == "hybrid"
        assert meta["hybrid_supported"] is True
        assert meta["similarity_score"] == 0.92
        assert meta["source"] == "s3://bucket/doc.pdf"

    def test_hybrid_retrieve_missing_bedrock_client(self, bedrock_kb_service):
        """hybrid_retrieve raises ValueError when bedrock_agent_client is None."""
        with pytest.raises(ValueError, match="Bedrock agent client required"):
            bedrock_kb_service.hybrid_retrieve(
                query="test",
                collection_id="ds-456",
                top_k=5,
                model_name="m",
            )

    def test_hybrid_retrieve_falls_back_on_validation_exception(self, bedrock_kb_service):
        """First hybrid call to unsupported KB falls back to semantic search."""
        mock_client = MagicMock()
        error_response = {"Error": {"Code": "ValidationException", "Message": "Hybrid search not supported"}}
        mock_client.retrieve.side_effect = [
            ClientError(error_response, "Retrieve"),
            {
                "retrievalResults": [
                    {
                        "content": {"text": "fallback result"},
                        "metadata": {},
                        "score": 0.8,
                        "location": {"s3Location": {"uri": "s3://b/d.pdf"}},
                    }
                ]
            },
        ]

        results = bedrock_kb_service.hybrid_retrieve(
            query="test",
            collection_id="ds-456",
            top_k=5,
            model_name="m",
            include_score=True,
            bedrock_agent_client=mock_client,
        )

        assert len(results) == 1
        assert results[0]["page_content"] == "fallback result"
        assert results[0]["metadata"]["actual_mode_used"] == "semantic"
        assert results[0]["metadata"]["hybrid_supported"] is False
        assert results[0]["metadata"]["retrieval_method"] == "hybrid"
        assert results[0]["metadata"]["similarity_score"] == 0.8
        assert mock_client.retrieve.call_count == 2

    def test_hybrid_retrieve_fallback_metadata_on_all_docs(self, bedrock_kb_service):
        """All documents in fallback response include correct metadata."""
        mock_client = MagicMock()
        error_response = {"Error": {"Code": "ValidationException", "Message": "Hybrid not supported"}}
        mock_client.retrieve.side_effect = [
            ClientError(error_response, "Retrieve"),
            {
                "retrievalResults": [
                    {
                        "content": {"text": "doc1"},
                        "metadata": {},
                        "score": 0.9,
                        "location": {"s3Location": {"uri": "s3://b/a.pdf"}},
                    },
                    {
                        "content": {"text": "doc2"},
                        "metadata": {},
                        "score": 0.7,
                        "location": {"s3Location": {"uri": "s3://b/b.pdf"}},
                    },
                ]
            },
        ]

        results = bedrock_kb_service.hybrid_retrieve(
            query="test",
            collection_id="ds-456",
            top_k=5,
            model_name="m",
            include_score=True,
            bedrock_agent_client=mock_client,
        )

        assert len(results) == 2
        for doc in results:
            assert doc["metadata"]["actual_mode_used"] == "semantic"
            assert doc["metadata"]["hybrid_supported"] is False
            assert doc["metadata"]["retrieval_method"] == "hybrid"

    def test_hybrid_retrieve_reraises_non_validation_client_error(self, bedrock_kb_service):
        """Non-ValidationException ClientErrors propagate normally."""
        mock_client = MagicMock()
        error_response = {"Error": {"Code": "AccessDeniedException", "Message": "No access"}}
        mock_client.retrieve.side_effect = ClientError(error_response, "Retrieve")

        with pytest.raises(ClientError):
            bedrock_kb_service.hybrid_retrieve(
                query="test", collection_id="ds-456", top_k=5, model_name="m", bedrock_agent_client=mock_client
            )

    def test_hybrid_retrieve_reraises_non_client_error(self, bedrock_kb_service):
        """Non-ClientError exceptions propagate normally."""
        mock_client = MagicMock()
        mock_client.retrieve.side_effect = RuntimeError("connection lost")

        with pytest.raises(RuntimeError, match="connection lost"):
            bedrock_kb_service.hybrid_retrieve(
                query="test", collection_id="ds-456", top_k=5, model_name="m", bedrock_agent_client=mock_client
            )

    def test_hybrid_retrieve_does_not_catch_auto_pause_exception(self, bedrock_kb_service):
        """Auto-pause ServiceUnavailableException propagates through fallback."""
        mock_client = MagicMock()
        error_response = {"Error": {"Code": "ValidationException", "Message": "The Aurora cluster is auto-paused"}}
        mock_client.retrieve.side_effect = ClientError(error_response, "Retrieve")

        with pytest.raises(ServiceUnavailableException, match="starting up"):
            bedrock_kb_service.hybrid_retrieve(
                query="test", collection_id="ds-456", top_k=5, model_name="m", bedrock_agent_client=mock_client
            )

    def test_hybrid_retrieve_propagates_non_hybrid_validation_exception(self, bedrock_kb_service):
        """Non-hybrid ValidationException (e.g., invalid filter) must NOT trigger fallback."""
        mock_client = MagicMock()
        error_response = {"Error": {"Code": "ValidationException", "Message": "Invalid filter expression"}}
        mock_client.retrieve.side_effect = ClientError(error_response, "Retrieve")

        with pytest.raises(ClientError) as exc_info:
            bedrock_kb_service.hybrid_retrieve(
                query="test",
                collection_id="ds-456",
                top_k=5,
                model_name="m",
                bedrock_agent_client=mock_client,
            )

        assert "Invalid filter expression" in str(exc_info.value)

    def test_hybrid_retrieve_propagates_fallback_failure(self, bedrock_kb_service):
        """If semantic fallback also fails, the error propagates."""
        mock_client = MagicMock()
        hybrid_error = {"Error": {"Code": "ValidationException", "Message": "Hybrid search is not supported"}}
        throttle_error = {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}}
        mock_client.retrieve.side_effect = [
            ClientError(hybrid_error, "Retrieve"),
            ClientError(throttle_error, "Retrieve"),
        ]

        with pytest.raises(ClientError) as exc_info:
            bedrock_kb_service.hybrid_retrieve(
                query="test",
                collection_id="ds-456",
                top_k=5,
                model_name="m",
                bedrock_agent_client=mock_client,
            )

        assert "ThrottlingException" in str(exc_info.value)
        assert mock_client.retrieve.call_count == 2
