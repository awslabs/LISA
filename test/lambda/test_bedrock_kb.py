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

"""Tests for Bedrock Knowledge Base utilities."""

from unittest.mock import MagicMock

import pytest
from models.domain_objects import (
    ChunkingStrategyType,
    IngestionJob,
    IngestionType,
    JobActionType,
    NoneChunkingStrategy,
    VectorStoreConfig,
)
from utilities.bedrock_kb import (
    add_default_pipeline_for_bedrock_kb,
    bulk_delete_documents_from_kb,
    delete_document_from_kb,
    ingest_bedrock_s3_documents,
    ingest_document_to_kb,
)


class TestIngestDocumentToKB:
    """Test document ingestion to Bedrock Knowledge Base."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client."""
        return MagicMock()

    @pytest.fixture
    def mock_bedrock_agent_client(self):
        """Create mock bedrock-agent client."""
        return MagicMock()

    @pytest.fixture
    def sample_job(self):
        """Sample ingestion job."""
        return IngestionJob(
            repository_id="test-repo",
            collection_id="test-collection",
            embedding_model="amazon.titan-embed-text-v1",
            chunk_strategy=NoneChunkingStrategy(),
            s3_path="s3://source-bucket/path/to/document.pdf",
            username="testuser",
        )

    @pytest.fixture
    def sample_repository(self):
        """Sample repository configuration."""
        return {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {
                "bedrockKnowledgeBaseId": "KB123456",
                "bedrockKnowledgeDatasourceId": "DS123456",
                "bedrockKnowledgeDatasourceS3Bucket": "kb-datasource-bucket",
            },
        }

    def test_ingest_document_to_kb_success(
        self, mock_s3_client, mock_bedrock_agent_client, sample_job, sample_repository
    ):
        """Test successful document ingestion."""
        # Act
        ingest_document_to_kb(
            s3_client=mock_s3_client,
            bedrock_agent_client=mock_bedrock_agent_client,
            job=sample_job,
            repository=sample_repository,
        )

        # Assert
        mock_s3_client.copy_object.assert_called_once_with(
            CopySource={"Bucket": "source-bucket", "Key": "path/to/document.pdf"},
            Bucket="kb-datasource-bucket",
            Key="document.pdf",
        )

        mock_s3_client.delete_object.assert_called_once_with(Bucket="source-bucket", Key="path/to/document.pdf")

        mock_bedrock_agent_client.start_ingestion_job.assert_called_once_with(
            knowledgeBaseId="KB123456",
            dataSourceId="DS123456",
        )


class TestDeleteDocumentFromKB:
    """Test document deletion from Bedrock Knowledge Base."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client."""
        return MagicMock()

    @pytest.fixture
    def mock_bedrock_agent_client(self):
        """Create mock bedrock-agent client."""
        return MagicMock()

    @pytest.fixture
    def sample_job(self):
        """Sample deletion job."""
        return IngestionJob(
            repository_id="test-repo",
            collection_id="test-collection",
            embedding_model="amazon.titan-embed-text-v1",
            chunk_strategy=NoneChunkingStrategy(),
            s3_path="s3://kb-datasource-bucket/document.pdf",
            username="testuser",
        )

    @pytest.fixture
    def sample_repository(self):
        """Sample repository configuration."""
        return {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {
                "bedrockKnowledgeBaseId": "KB123456",
                "bedrockKnowledgeDatasourceId": "DS123456",
                "bedrockKnowledgeDatasourceS3Bucket": "kb-datasource-bucket",
            },
        }

    def test_delete_document_from_kb_success(
        self, mock_s3_client, mock_bedrock_agent_client, sample_job, sample_repository
    ):
        """Test successful document deletion."""
        # Act
        delete_document_from_kb(
            s3_client=mock_s3_client,
            bedrock_agent_client=mock_bedrock_agent_client,
            job=sample_job,
            repository=sample_repository,
        )

        # Assert
        mock_s3_client.delete_object.assert_called_once_with(Bucket="kb-datasource-bucket", Key="document.pdf")

        mock_bedrock_agent_client.start_ingestion_job.assert_called_once_with(
            knowledgeBaseId="KB123456",
            dataSourceId="DS123456",
        )


class TestBulkDeleteDocumentsFromKB:
    """Test bulk document deletion from Bedrock Knowledge Base."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client."""
        return MagicMock()

    @pytest.fixture
    def mock_bedrock_agent_client(self):
        """Create mock bedrock-agent client."""
        return MagicMock()

    @pytest.fixture
    def sample_repository(self):
        """Sample repository configuration."""
        return {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {
                "bedrockKnowledgeBaseId": "KB123456",
                "bedrockKnowledgeDatasourceId": "DS123456",
                "bedrockKnowledgeDatasourceS3Bucket": "kb-datasource-bucket",
            },
        }

    def test_bulk_delete_small_batch(self, mock_s3_client, mock_bedrock_agent_client, sample_repository):
        """Test bulk delete with small batch."""
        # Arrange
        s3_paths = [
            "s3://kb-datasource-bucket/doc1.pdf",
            "s3://kb-datasource-bucket/doc2.pdf",
            "s3://kb-datasource-bucket/doc3.pdf",
        ]

        # Act
        bulk_delete_documents_from_kb(
            s3_client=mock_s3_client,
            bedrock_agent_client=mock_bedrock_agent_client,
            repository=sample_repository,
            s3_paths=s3_paths,
        )

        # Assert
        mock_s3_client.delete_objects.assert_called_once_with(
            Bucket="kb-datasource-bucket",
            Delete={"Objects": [{"Key": "doc1.pdf"}, {"Key": "doc2.pdf"}, {"Key": "doc3.pdf"}]},
        )

        mock_bedrock_agent_client.start_ingestion_job.assert_called_once_with(
            knowledgeBaseId="KB123456",
            dataSourceId="DS123456",
        )

    def test_bulk_delete_large_batch(self, mock_s3_client, mock_bedrock_agent_client, sample_repository):
        """Test bulk delete with batch size exceeding 1000."""
        # Arrange - Create 1500 paths to test batching
        s3_paths = [f"s3://kb-datasource-bucket/doc{i}.pdf" for i in range(1500)]

        # Act
        bulk_delete_documents_from_kb(
            s3_client=mock_s3_client,
            bedrock_agent_client=mock_bedrock_agent_client,
            repository=sample_repository,
            s3_paths=s3_paths,
        )

        # Assert - Should be called twice (1000 + 500)
        assert mock_s3_client.delete_objects.call_count == 2

        # Verify first batch has 1000 items
        first_call_args = mock_s3_client.delete_objects.call_args_list[0]
        assert len(first_call_args[1]["Delete"]["Objects"]) == 1000

        # Verify second batch has 500 items
        second_call_args = mock_s3_client.delete_objects.call_args_list[1]
        assert len(second_call_args[1]["Delete"]["Objects"]) == 500

        # Verify ingestion job started once
        mock_bedrock_agent_client.start_ingestion_job.assert_called_once()


class TestAddDefaultPipelineForBedrockKB:
    """Test automatic pipeline addition for Bedrock KB repositories."""

    def test_add_default_pipeline_when_none_exists(self):
        """Test adding default pipeline when no pipelines configured."""
        # Arrange
        from models.domain_objects import BedrockKnowledgeBaseConfig

        bedrock_config = BedrockKnowledgeBaseConfig(
            bedrockKnowledgeBaseName="test-kb",
            bedrockKnowledgeBaseId="KB123456",
            bedrockKnowledgeDatasourceName="test-datasource",
            bedrockKnowledgeDatasourceId="DS123456",
            bedrockKnowledgeDatasourceS3Bucket="kb-datasource-bucket",
        )

        vector_store_config = VectorStoreConfig(
            repositoryId="test-repo",
            type="bedrock_knowledge_base",
            embeddingModelId="amazon.titan-embed-text-v1",
            bedrockKnowledgeBaseConfig=bedrock_config,
        )

        # Act
        add_default_pipeline_for_bedrock_kb(vector_store_config)

        # Assert
        assert vector_store_config.pipelines is not None
        assert len(vector_store_config.pipelines) == 1

        pipeline = vector_store_config.pipelines[0]
        assert pipeline.s3Bucket == "kb-datasource-bucket"
        assert pipeline.s3Prefix == ""
        assert pipeline.trigger == "event"
        assert pipeline.autoRemove is True
        assert pipeline.chunkingStrategy.type == ChunkingStrategyType.NONE

    def test_add_default_pipeline_appends_to_existing(self):
        """Test adding default pipeline appends to existing pipelines."""
        # Arrange
        from models.domain_objects import BedrockKnowledgeBaseConfig, PipelineConfig, PipelineTrigger

        bedrock_config = BedrockKnowledgeBaseConfig(
            bedrockKnowledgeBaseName="test-kb",
            bedrockKnowledgeBaseId="KB123456",
            bedrockKnowledgeDatasourceName="test-datasource",
            bedrockKnowledgeDatasourceId="DS123456",
            bedrockKnowledgeDatasourceS3Bucket="kb-datasource-bucket",
        )

        existing_pipeline = PipelineConfig(
            s3Bucket="custom-bucket",
            s3Prefix="custom/",
            collectinoId=bedrock_config.bedrockKnowledgeDatasourceId,
            trigger=PipelineTrigger.SCHEDULE,
            autoRemove=False,
            chunkingStrategy=NoneChunkingStrategy(type=ChunkingStrategyType.NONE),
        )

        vector_store_config = VectorStoreConfig(
            repositoryId="test-repo",
            type="bedrock_knowledge_base",
            embeddingModelId="amazon.titan-embed-text-v1",
            bedrockKnowledgeBaseConfig=bedrock_config,
            pipelines=[existing_pipeline],
        )

        # Act
        add_default_pipeline_for_bedrock_kb(vector_store_config)

        # Assert
        assert len(vector_store_config.pipelines) == 2
        assert vector_store_config.pipelines[0].s3Bucket == "custom-bucket"
        assert vector_store_config.pipelines[1].s3Bucket == "kb-datasource-bucket"

    def test_no_pipeline_added_when_no_bedrock_config(self):
        """Test no pipeline added when bedrockKnowledgeBaseConfig is None."""
        # Arrange
        vector_store_config = VectorStoreConfig(
            repositoryId="test-repo",
            type="opensearch",
            embeddingModelId="amazon.titan-embed-text-v1",
        )

        # Act
        add_default_pipeline_for_bedrock_kb(vector_store_config)

        # Assert
        assert vector_store_config.pipelines is None


class TestIngestBedrockS3Documents:
    """Test discovery and ingestion of existing documents in Bedrock KB S3 bucket."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client."""
        return MagicMock()

    @pytest.fixture
    def mock_ingestion_job_repo(self):
        """Create mock ingestion job repository."""
        return MagicMock()

    @pytest.fixture
    def mock_ingestion_service(self):
        """Create mock ingestion service."""
        return MagicMock()

    def test_ingest_existing_documents_success(self, mock_s3_client, mock_ingestion_job_repo, mock_ingestion_service):
        """Test successful discovery and ingestion of existing documents."""
        # Arrange
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "doc1.pdf"},
                {"Key": "doc2.txt"},
                {"Key": "doc3.docx"},
            ]
        }

        # Act
        discovered, skipped = ingest_bedrock_s3_documents(
            s3_client=mock_s3_client,
            ingestion_job_repository=mock_ingestion_job_repo,
            ingestion_service=mock_ingestion_service,
            repository_id="test-repo",
            collection_id="test-collection",
            s3_bucket="kb-datasource-bucket",
            embedding_model="amazon.titan-embed-text-v1",
        )

        # Assert
        assert discovered == 3
        assert skipped == 0

        # Verify job was created and submitted
        mock_ingestion_job_repo.save.assert_called_once()
        mock_ingestion_service.submit_create_job.assert_called_once()

        # Verify job properties
        saved_job = mock_ingestion_job_repo.save.call_args[0][0]
        assert saved_job.repository_id == "test-repo"
        assert saved_job.collection_id == "test-collection"
        assert saved_job.ingestion_type == IngestionType.EXISTING
        assert saved_job.job_type == JobActionType.DOCUMENT_BATCH_INGESTION
        assert len(saved_job.s3_paths) == 3
        assert "s3://kb-datasource-bucket/doc1.pdf" in saved_job.s3_paths

    def test_ingest_skips_metadata_files(self, mock_s3_client, mock_ingestion_job_repo, mock_ingestion_service):
        """Test that metadata files are skipped."""
        # Arrange
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "doc1.pdf"},
                {"Key": "doc1.pdf.metadata.json"},
                {"Key": "doc2.txt"},
                {"Key": "doc2.txt.metadata.json"},
            ]
        }

        # Act
        discovered, skipped = ingest_bedrock_s3_documents(
            s3_client=mock_s3_client,
            ingestion_job_repository=mock_ingestion_job_repo,
            ingestion_service=mock_ingestion_service,
            repository_id="test-repo",
            collection_id="test-collection",
            s3_bucket="kb-datasource-bucket",
            embedding_model="amazon.titan-embed-text-v1",
        )

        # Assert
        assert discovered == 2
        assert skipped == 2

        saved_job = mock_ingestion_job_repo.save.call_args[0][0]
        assert len(saved_job.s3_paths) == 2
        assert "s3://kb-datasource-bucket/doc1.pdf" in saved_job.s3_paths
        assert "s3://kb-datasource-bucket/doc2.txt" in saved_job.s3_paths

    def test_ingest_handles_empty_bucket(self, mock_s3_client, mock_ingestion_job_repo, mock_ingestion_service):
        """Test handling of empty S3 bucket."""
        # Arrange
        mock_s3_client.list_objects_v2.return_value = {}

        # Act
        discovered, skipped = ingest_bedrock_s3_documents(
            s3_client=mock_s3_client,
            ingestion_job_repository=mock_ingestion_job_repo,
            ingestion_service=mock_ingestion_service,
            repository_id="test-repo",
            collection_id="test-collection",
            s3_bucket="kb-datasource-bucket",
            embedding_model="amazon.titan-embed-text-v1",
        )

        # Assert
        assert discovered == 0
        assert skipped == 0
        mock_ingestion_job_repo.save.assert_not_called()
        mock_ingestion_service.submit_create_job.assert_not_called()

    def test_ingest_handles_large_batch(self, mock_s3_client, mock_ingestion_job_repo, mock_ingestion_service):
        """Test batching for large number of documents."""
        # Arrange - Create 250 documents to test batching (should create 3 jobs)
        contents = [{"Key": f"doc{i}.pdf"} for i in range(250)]
        mock_s3_client.list_objects_v2.return_value = {"Contents": contents}

        # Act
        discovered, skipped = ingest_bedrock_s3_documents(
            s3_client=mock_s3_client,
            ingestion_job_repository=mock_ingestion_job_repo,
            ingestion_service=mock_ingestion_service,
            repository_id="test-repo",
            collection_id="test-collection",
            s3_bucket="kb-datasource-bucket",
            embedding_model="amazon.titan-embed-text-v1",
        )

        # Assert
        assert discovered == 250
        assert skipped == 0

        # Should create 3 jobs (100 + 100 + 50)
        assert mock_ingestion_job_repo.save.call_count == 3
        assert mock_ingestion_service.submit_create_job.call_count == 3

        # Verify batch sizes
        first_job = mock_ingestion_job_repo.save.call_args_list[0][0][0]
        assert len(first_job.s3_paths) == 100

        second_job = mock_ingestion_job_repo.save.call_args_list[1][0][0]
        assert len(second_job.s3_paths) == 100

        third_job = mock_ingestion_job_repo.save.call_args_list[2][0][0]
        assert len(third_job.s3_paths) == 50

    def test_ingest_handles_s3_error(self, mock_s3_client, mock_ingestion_job_repo, mock_ingestion_service):
        """Test graceful handling of S3 errors."""
        # Arrange
        mock_s3_client.list_objects_v2.side_effect = Exception("S3 error")

        # Act - Should not raise exception
        discovered, skipped = ingest_bedrock_s3_documents(
            s3_client=mock_s3_client,
            ingestion_job_repository=mock_ingestion_job_repo,
            ingestion_service=mock_ingestion_service,
            repository_id="test-repo",
            collection_id="test-collection",
            s3_bucket="kb-datasource-bucket",
            embedding_model="amazon.titan-embed-text-v1",
        )

        # Assert
        assert discovered == 0
        assert skipped == 0
        mock_ingestion_job_repo.save.assert_not_called()
