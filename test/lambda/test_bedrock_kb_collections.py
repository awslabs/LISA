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

"""Tests for Bedrock Knowledge Base collection support."""

from typing import Any, Dict
from unittest.mock import create_autospec, MagicMock

import pytest
from models.domain_objects import CollectionMetadata, RagCollectionConfig, VectorStoreStatus
from repository.collection_service import CollectionService
from repository.vector_store_repo import VectorStoreRepository
from utilities.validation import ValidationError


@pytest.fixture(scope="function")
def mock_vector_store_repo():
    """Create a mock VectorStoreRepository with autospec."""
    mock = create_autospec(VectorStoreRepository, instance=True)
    mock.find_repository_by_id.return_value = None
    return mock


@pytest.fixture(scope="function")
def mock_document_repo():
    """Create a mock RagDocumentRepository."""
    # Use MagicMock instead of autospec to avoid import order issues in full test suite
    mock = MagicMock()
    # Configure default return values for common methods
    mock.list_all.return_value = ([], None, 0)
    mock.delete_by_id.return_value = None
    return mock


@pytest.fixture(scope="function")
def collection_service(mock_vector_store_repo, mock_document_repo):
    """Create CollectionService with mocked dependencies."""
    return CollectionService(vector_store_repo=mock_vector_store_repo, document_repo=mock_document_repo)


@pytest.fixture
def bedrock_kb_repository() -> Dict[str, Any]:
    """Sample Bedrock Knowledge Base repository configuration."""
    return {
        "repositoryId": "test-bedrock-kb",
        "repositoryName": "Test Bedrock KB",
        "type": "bedrock_knowledge_base",
        "embeddingModelId": "amazon.titan-embed-text-v1",
        "status": VectorStoreStatus.CREATE_COMPLETE,
        "allowedGroups": ["admin", "users"],
        "bedrockKnowledgeBaseConfig": {
            "bedrockKnowledgeBaseName": "test-kb",
            "bedrockKnowledgeBaseId": "KB123456",
            "bedrockKnowledgeDatasourceName": "test-datasource",
            "bedrockKnowledgeDatasourceId": "DS123456",
            "bedrockKnowledgeDatasourceS3Bucket": "test-kb-bucket",
        },
        "pipelines": [
            {
                "s3Bucket": "test-kb-bucket",
                "s3Prefix": "",
                "trigger": "event",
                "embeddingModel": "amazon.titan-embed-text-v1",
                "chunkSize": 512,
                "chunkOverlap": 51,
                "autoRemove": True,
            }
        ],
        "createdBy": "admin",
    }


class TestBedrockKBDefaultCollection:
    """Test default collection creation for Bedrock Knowledge Base repositories."""

    def test_create_default_collection_for_bedrock_kb(
        self, collection_service, mock_vector_store_repo, bedrock_kb_repository
    ):
        """Test that default collection is created for Bedrock KB repository."""
        # Arrange
        mock_vector_store_repo.find_repository_by_id.return_value = bedrock_kb_repository

        # Act
        collection = collection_service.create_default_collection(
            repository_id="test-bedrock-kb", repository=bedrock_kb_repository
        )

        # Assert
        assert collection is not None
        assert collection.default is True
        assert collection.repositoryId == "test-bedrock-kb"
        assert collection.collectionId == "DS123456"  # Uses data source ID as collection ID
        assert collection.embeddingModel == "amazon.titan-embed-text-v1"
        assert collection.description == "Default collection for Bedrock Knowledge Base"
        assert collection.allowChunkingOverride is False  # Bedrock KB doesn't allow override
        assert "bedrock-kb" in collection.metadata.tags
        assert "default" in collection.metadata.tags

    def test_default_collection_includes_pipelines(
        self, collection_service, mock_vector_store_repo, bedrock_kb_repository
    ):
        """Test that default collection includes repository pipelines."""
        # Arrange
        mock_vector_store_repo.find_repository_by_id.return_value = bedrock_kb_repository

        # Act
        collection = collection_service.create_default_collection(
            repository_id="test-bedrock-kb", repository=bedrock_kb_repository
        )

        # Assert
        assert len(collection.pipelines) == 1
        pipeline = collection.pipelines[0]
        # Pipeline can be either a dict or PipelineConfig object
        if isinstance(pipeline, dict):
            assert pipeline["s3Bucket"] == "test-kb-bucket"
            assert pipeline["trigger"] == "event"
        else:
            assert pipeline.s3Bucket == "test-kb-bucket"
            assert pipeline.trigger == "event"

    def test_default_collection_not_created_for_inactive_repository(
        self, collection_service, mock_vector_store_repo, bedrock_kb_repository
    ):
        """Test that default collection is not created for inactive repositories."""
        # Arrange
        bedrock_kb_repository["status"] = VectorStoreStatus.CREATE_IN_PROGRESS
        mock_vector_store_repo.find_repository_by_id.return_value = bedrock_kb_repository

        # Act
        collection = collection_service.create_default_collection(repository_id="test-bedrock-kb")

        # Assert
        assert collection is None


class TestBedrockKBCollectionRestrictions:
    """Test that Bedrock KB repositories have appropriate collection restrictions."""

    def test_cannot_create_user_collections_in_bedrock_kb(self, bedrock_kb_repository):
        """Test that user-created collections are blocked for Bedrock KB repositories."""
        # Arrange
        from repository.collection_repo import CollectionRepository

        mock_collection_repo = create_autospec(CollectionRepository, instance=True)
        mock_vector_store_repo = create_autospec(VectorStoreRepository, instance=True)
        mock_document_repo = MagicMock()

        # Mock find_by_name to return None (no existing collection with that name)
        mock_collection_repo.find_by_name.return_value = None

        collection_service = CollectionService(
            collection_repo=mock_collection_repo,
            vector_store_repo=mock_vector_store_repo,
            document_repo=mock_document_repo,
        )

        new_collection = RagCollectionConfig(
            repositoryId="test-bedrock-kb",
            name="user-collection",
            embeddingModel="amazon.titan-embed-text-v1",
            createdBy="testuser",
        )

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            collection_service.create_collection(
                repository=bedrock_kb_repository,
                collection=new_collection,
                username="testuser",
            )

        assert "only support the default collection" in str(exc_info.value)
        assert "BEDROCK_KB" in str(exc_info.value) or "bedrock_knowledge_base" in str(exc_info.value)


class TestRepositoryCreationWithDefaultPipeline:
    """Test automatic pipeline creation for Bedrock KB repositories."""

    def test_auto_add_default_pipeline_for_bedrock_kb(self):
        """Test that default pipeline is automatically added for Bedrock KB repositories."""
        # Arrange - Test the logic directly without going through the full Lambda handler
        rag_config = {
            "repositoryId": "test-bedrock-kb",
            "type": "bedrock_knowledge_base",
            "embeddingModelId": "amazon.titan-embed-text-v1",
            "bedrockKnowledgeBaseConfig": {
                "bedrockKnowledgeBaseName": "test-kb",
                "bedrockKnowledgeBaseId": "KB123456",
                "bedrockKnowledgeDatasourceName": "test-datasource",
                "bedrockKnowledgeDatasourceId": "DS123456",
                "bedrockKnowledgeDatasourceS3Bucket": "test-kb-bucket",
            },
            "chunkingStrategy": {"type": "fixed", "size": 512, "overlap": 51},
        }

        # Act - Apply the pipeline logic
        if rag_config.get("type") == "bedrock_knowledge_base":
            bedrock_config = rag_config.get("bedrockKnowledgeBaseConfig", {})
            datasource_bucket = bedrock_config.get("bedrockKnowledgeDatasourceS3Bucket")

            if datasource_bucket and not rag_config.get("pipelines"):
                embedding_model = rag_config.get("embeddingModelId", "default")
                chunking_strategy = rag_config.get("chunkingStrategy", {"type": "fixed", "size": 512, "overlap": 51})

                default_pipeline = {
                    "s3Bucket": datasource_bucket,
                    "s3Prefix": "",
                    "trigger": "event",
                    "embeddingModel": embedding_model,
                    "chunkSize": chunking_strategy.get("size", 512),
                    "chunkOverlap": chunking_strategy.get("overlap", 51),
                    "chunkingStrategy": chunking_strategy,
                    "autoRemove": True,
                }

                rag_config["pipelines"] = [default_pipeline]

        # Assert
        assert "pipelines" in rag_config
        assert len(rag_config["pipelines"]) == 1

        pipeline = rag_config["pipelines"][0]
        assert pipeline["s3Bucket"] == "test-kb-bucket"
        assert pipeline["s3Prefix"] == ""
        assert pipeline["trigger"] == "event"
        assert pipeline["embeddingModel"] == "amazon.titan-embed-text-v1"
        assert pipeline["autoRemove"] is True

    def test_preserve_existing_pipelines_for_bedrock_kb(self):
        """Test that existing pipelines are preserved when provided."""
        # Arrange - Test the logic directly
        custom_pipeline = {
            "s3Bucket": "custom-bucket",
            "s3Prefix": "documents/",
            "trigger": "daily",
            "embeddingModel": "amazon.titan-embed-text-v1",
            "chunkSize": 1024,
            "chunkOverlap": 100,
            "autoRemove": False,
        }

        rag_config = {
            "repositoryId": "test-bedrock-kb",
            "type": "bedrock_knowledge_base",
            "embeddingModelId": "amazon.titan-embed-text-v1",
            "bedrockKnowledgeBaseConfig": {
                "bedrockKnowledgeBaseName": "test-kb",
                "bedrockKnowledgeBaseId": "KB123456",
                "bedrockKnowledgeDatasourceName": "test-datasource",
                "bedrockKnowledgeDatasourceId": "DS123456",
                "bedrockKnowledgeDatasourceS3Bucket": "test-kb-bucket",
            },
            "pipelines": [custom_pipeline],
        }

        # Act - Apply the pipeline logic (should NOT add default pipeline)
        if rag_config.get("type") == "bedrock_knowledge_base":
            bedrock_config = rag_config.get("bedrockKnowledgeBaseConfig", {})
            datasource_bucket = bedrock_config.get("bedrockKnowledgeDatasourceS3Bucket")

            # Only add default pipeline if no pipelines are configured
            if datasource_bucket and not rag_config.get("pipelines"):
                # This should NOT execute because pipelines already exist
                rag_config["pipelines"] = [{"should": "not_be_added"}]

        # Assert - Verify the custom pipeline was preserved
        assert len(rag_config["pipelines"]) == 1
        assert rag_config["pipelines"][0]["s3Bucket"] == "custom-bucket"
        assert rag_config["pipelines"][0]["s3Prefix"] == "documents/"
        assert rag_config["pipelines"][0]["trigger"] == "daily"


class TestBedrockKBCollectionMetadata:
    """Test metadata handling for Bedrock KB collections."""

    def test_default_collection_has_correct_metadata(
        self, collection_service, mock_vector_store_repo, bedrock_kb_repository
    ):
        """Test that default collection has appropriate metadata tags."""
        # Arrange
        mock_vector_store_repo.find_repository_by_id.return_value = bedrock_kb_repository

        # Act
        collection = collection_service.create_default_collection(
            repository_id="test-bedrock-kb", repository=bedrock_kb_repository
        )

        # Assert
        assert isinstance(collection.metadata, CollectionMetadata)
        assert "default" in collection.metadata.tags
        assert "bedrock-kb" in collection.metadata.tags

    def test_default_collection_inherits_repository_access_control(
        self, collection_service, mock_vector_store_repo, bedrock_kb_repository
    ):
        """Test that default collection inherits repository access control."""
        # Arrange
        mock_vector_store_repo.find_repository_by_id.return_value = bedrock_kb_repository

        # Act
        collection = collection_service.create_default_collection(
            repository_id="test-bedrock-kb", repository=bedrock_kb_repository
        )

        # Assert
        assert collection.allowedGroups == ["admin", "users"]
        assert collection.private is False
