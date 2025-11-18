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
from unittest.mock import MagicMock, create_autospec, patch

import pytest
from models.domain_objects import IngestionJob, IngestionType, NoneChunkingStrategy
from repository.rag_document_repo import RagDocumentRepository
from repository.services.bedrock_kb_repository_service import BedrockKBRepositoryService


@pytest.fixture
def bedrock_kb_repository():
    """Fixture providing Bedrock KB repository configuration."""
    return {
        "repositoryId": "test-bedrock-repo",
        "type": "bedrock_knowledge_base",
        "bedrockKnowledgeBaseConfig": {
            "bedrockKnowledgeBaseId": "kb-test-123",
            "bedrockKnowledgeDatasourceId": "ds-test-456",
            "bedrockKnowledgeDatasourceS3Bucket": "test-kb-bucket"
        }
    }


@pytest.fixture
def bedrock_kb_service(bedrock_kb_repository):
    """Fixture providing BedrockKBRepositoryService instance."""
    return BedrockKBRepositoryService(bedrock_kb_repository)


@pytest.fixture
def mock_rag_document_repo():
    """Fixture providing mocked RagDocumentRepository with autospec."""
    return create_autospec(RagDocumentRepository, instance=True)


class TestBedrockKBRepositoryService:
    """Test suite for BedrockKBRepositoryService."""

    def test_supports_custom_collections(self, bedrock_kb_service):
        """Test that Bedrock KB does not support custom collections."""
        assert bedrock_kb_service.supports_custom_collections() is False

    def test_should_create_default_collection(self, bedrock_kb_service):
        """Test that Bedrock KB does not create default collections."""
        assert bedrock_kb_service.should_create_default_collection() is False

    def test_get_collection_id_from_config(self, bedrock_kb_service):
        """Test extracting collection ID (data source ID) from config."""
        pipeline_config = {"embeddingModel": "test-model"}
        
        collection_id = bedrock_kb_service.get_collection_id_from_config(pipeline_config)
        
        assert collection_id == "ds-test-456"

    def test_get_collection_id_missing_data_source(self):
        """Test error when data source ID is missing."""
        repository = {
            "repositoryId": "test-repo",
            "type": "bedrock_knowledge_base",
            "bedrockKnowledgeBaseConfig": {}
        }
        service = BedrockKBRepositoryService(repository)
        
        with pytest.raises(ValueError, match="missing data source ID"):
            service.get_collection_id_from_config({})

    def test_validate_document_source_valid(self, bedrock_kb_service):
        """Test validating document from correct KB bucket."""
        s3_path = "s3://test-kb-bucket/document.pdf"
        
        result = bedrock_kb_service.validate_document_source(s3_path)
        
        assert result == s3_path

    def test_validate_document_source_wrong_bucket(self, bedrock_kb_service):
        """Test normalizing document from wrong bucket."""
        s3_path = "s3://wrong-bucket/document.pdf"
        
        result = bedrock_kb_service.validate_document_source(s3_path)
        
        # Should normalize to KB bucket
        assert result == "s3://test-kb-bucket/document.pdf"

    def test_get_vector_store_client_returns_none(self, bedrock_kb_service):
        """Test that Bedrock KB does not use vector store clients."""
        client = bedrock_kb_service.get_vector_store_client("test-collection", None)
        
        assert client is None

    @patch.dict(os.environ, {
        "RAG_DOCUMENT_TABLE": "test-doc-table",
        "RAG_SUB_DOCUMENT_TABLE": "test-subdoc-table"
    })
    def test_ingest_document_new(self, bedrock_kb_service, mock_rag_document_repo):
        """Test ingesting a new document to Bedrock KB."""
        job = IngestionJob(
            repository_id="test-bedrock-repo",
            collection_id="ds-test-456",
            s3_path="s3://test-kb-bucket/doc.pdf",
            username="test-user",
            ingestion_type=IngestionType.MANUAL,
            chunk_strategy=NoneChunkingStrategy(),
        )
        
        # Mock repository to return no existing documents
        mock_rag_document_repo.find_by_source.return_value = iter([])
        
        with patch("repository.services.bedrock_kb_repository_service.RagDocumentRepository",
                   return_value=mock_rag_document_repo):
            result = bedrock_kb_service.ingest_document(job, [], [])
        
        # Verify document was saved
        assert mock_rag_document_repo.save.called
        saved_doc = mock_rag_document_repo.save.call_args[0][0]
        assert saved_doc.source == "s3://test-kb-bucket/doc.pdf"
        assert saved_doc.subdocs == []  # KB manages chunks
        assert isinstance(saved_doc.chunk_strategy, NoneChunkingStrategy)

    def test_retrieve_documents(self, bedrock_kb_service):
        """Test retrieving documents from Bedrock KB."""
        mock_bedrock_client = MagicMock()
        mock_bedrock_client.retrieve.return_value = {
            "retrievalResults": [
                {
                    "content": {"text": "Test content"},
                    "metadata": {"source": "doc1.pdf"},
                    "score": 0.95,
                    "location": {"s3Location": {"uri": "s3://bucket/doc1.pdf"}}
                }
            ]
        }
        
        results = bedrock_kb_service.retrieve_documents(
            query="test query",
            collection_id="ds-test-456",
            top_k=5,
            bedrock_agent_client=mock_bedrock_client
        )
        
        assert len(results) == 1
        assert results[0]["content"] == "Test content"
        assert results[0]["score"] == 0.95
        
        # Verify API call
        mock_bedrock_client.retrieve.assert_called_once()
        call_args = mock_bedrock_client.retrieve.call_args[1]
        assert call_args["knowledgeBaseId"] == "kb-test-123"
        assert call_args["retrievalQuery"]["text"] == "test query"

    def test_retrieve_documents_missing_client(self, bedrock_kb_service):
        """Test error when Bedrock client is missing."""
        with pytest.raises(ValueError, match="Bedrock agent client required"):
            bedrock_kb_service.retrieve_documents(
                query="test",
                collection_id="ds-test-456",
                top_k=5,
                bedrock_agent_client=None
            )
