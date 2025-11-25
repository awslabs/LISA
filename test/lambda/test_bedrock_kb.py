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
from models.domain_objects import IngestionJob, IngestionType, JobActionType, NoneChunkingStrategy
from utilities.bedrock_kb import (
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
            dataSourceId="test-collection",
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
            dataSourceId="test-collection",
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
            data_source_id="DS123456",
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
            data_source_id="DS123456",
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


class TestGetDatasourceBucketForCollection:
    """Test getting datasource bucket for a collection."""

    def test_get_bucket_legacy_format(self):
        """Test getting bucket from legacy format."""
        from utilities.bedrock_kb import get_datasource_bucket_for_collection

        # Arrange
        repository = {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {
                "bedrockKnowledgeDatasourceS3Bucket": "legacy-bucket",
            },
        }

        # Act
        result = get_datasource_bucket_for_collection(repository, "test-collection")

        # Assert
        assert result == "legacy-bucket"

    def test_get_bucket_from_pipelines(self):
        """Test getting bucket from pipelines array."""
        from utilities.bedrock_kb import get_datasource_bucket_for_collection

        # Arrange
        repository = {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {},
            "pipelines": [
                {"collectionId": "collection-1", "s3Bucket": "bucket-1"},
                {"collectionId": "collection-2", "s3Bucket": "bucket-2"},
            ],
        }

        # Act
        result = get_datasource_bucket_for_collection(repository, "collection-2")

        # Assert
        assert result == "bucket-2"

    def test_get_bucket_from_data_sources(self):
        """Test getting bucket from dataSources array."""
        from utilities.bedrock_kb import get_datasource_bucket_for_collection

        # Arrange
        repository = {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {
                "dataSources": [
                    {"id": "ds-1", "s3Uri": "s3://bucket-1/prefix1/"},
                    {"id": "ds-2", "s3Uri": "s3://bucket-2/"},
                ]
            },
        }

        # Act
        result = get_datasource_bucket_for_collection(repository, "ds-2")

        # Assert
        assert result == "bucket-2"

    def test_get_bucket_invalid_s3_uri(self):
        """Test handling of invalid S3 URI format."""
        from utilities.bedrock_kb import get_datasource_bucket_for_collection

        # Arrange
        repository = {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {
                "dataSources": [
                    {"id": "ds-1", "s3Uri": "invalid-uri"},
                ]
            },
        }

        # Act & Assert
        with pytest.raises(ValueError, match="invalid s3Uri format"):
            get_datasource_bucket_for_collection(repository, "ds-1")

    def test_get_bucket_not_found(self):
        """Test handling when bucket configuration is not found."""
        from utilities.bedrock_kb import get_datasource_bucket_for_collection

        # Arrange
        repository = {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {},
            "pipelines": [],
        }

        # Act & Assert
        with pytest.raises(ValueError, match="Cannot determine S3 bucket"):
            get_datasource_bucket_for_collection(repository, "missing-collection")

    def test_get_bucket_from_pipelines_object_format(self):
        """Test getting bucket from pipelines with object format."""
        from utilities.bedrock_kb import get_datasource_bucket_for_collection

        # Arrange
        class Pipeline:
            def __init__(self, collection_id, s3_bucket):
                self.collectionId = collection_id
                self.s3Bucket = s3_bucket

        repository = {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {},
            "pipelines": [
                Pipeline("collection-1", "bucket-1"),
            ],
        }

        # Act
        result = get_datasource_bucket_for_collection(repository, "collection-1")

        # Assert
        assert result == "bucket-1"


class TestIngestDocumentToKBWithMultipleFormats:
    """Test document ingestion with different repository config formats."""

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
            s3_path="s3://source-bucket/document.pdf",
            username="testuser",
        )

    def test_ingest_with_pipelines_config(self, mock_s3_client, mock_bedrock_agent_client, sample_job):
        """Test ingestion with pipelines configuration."""
        from utilities.bedrock_kb import ingest_document_to_kb

        # Arrange
        repository = {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {
                "knowledgeBaseId": "KB123",
            },
            "pipelines": [
                {"collectionId": "test-collection", "s3Bucket": "kb-bucket"},
            ],
        }

        # Act
        ingest_document_to_kb(mock_s3_client, mock_bedrock_agent_client, sample_job, repository)

        # Assert
        mock_s3_client.copy_object.assert_called_once()
        assert mock_s3_client.copy_object.call_args[1]["Bucket"] == "kb-bucket"

    def test_ingest_with_data_sources_config(self, mock_s3_client, mock_bedrock_agent_client, sample_job):
        """Test ingestion with dataSources configuration."""
        from utilities.bedrock_kb import ingest_document_to_kb

        # Arrange
        repository = {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {
                "knowledgeBaseId": "KB123",
                "dataSources": [
                    {"id": "test-collection", "s3Uri": "s3://kb-bucket/prefix/"},
                ],
            },
        }

        # Act
        ingest_document_to_kb(mock_s3_client, mock_bedrock_agent_client, sample_job, repository)

        # Assert
        mock_s3_client.copy_object.assert_called_once()
        assert mock_s3_client.copy_object.call_args[1]["Bucket"] == "kb-bucket"

    def test_ingest_missing_kb_id(self, mock_s3_client, mock_bedrock_agent_client, sample_job):
        """Test ingestion with missing knowledge base ID."""
        from utilities.bedrock_kb import ingest_document_to_kb

        # Arrange
        repository = {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {},
            "pipelines": [
                {"collectionId": "test-collection", "s3Bucket": "kb-bucket"},
            ],
        }

        # Act & Assert
        with pytest.raises(ValueError, match="missing required field"):
            ingest_document_to_kb(mock_s3_client, mock_bedrock_agent_client, sample_job, repository)


class TestDeleteDocumentFromKBWithMultipleFormats:
    """Test document deletion with different repository config formats."""

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
            s3_path="s3://kb-bucket/document.pdf",
            username="testuser",
        )

    def test_delete_with_pipelines_config(self, mock_s3_client, mock_bedrock_agent_client, sample_job):
        """Test deletion with pipelines configuration."""
        from utilities.bedrock_kb import delete_document_from_kb

        # Arrange
        repository = {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {
                "knowledgeBaseId": "KB123",
            },
            "pipelines": [
                {"collectionId": "test-collection", "s3Bucket": "kb-bucket"},
            ],
        }

        # Act
        delete_document_from_kb(mock_s3_client, mock_bedrock_agent_client, sample_job, repository)

        # Assert
        mock_s3_client.delete_object.assert_called_once()
        assert mock_s3_client.delete_object.call_args[1]["Bucket"] == "kb-bucket"

    def test_delete_missing_kb_id(self, mock_s3_client, mock_bedrock_agent_client, sample_job):
        """Test deletion with missing knowledge base ID."""
        from utilities.bedrock_kb import delete_document_from_kb

        # Arrange
        repository = {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {},
            "pipelines": [
                {"collectionId": "test-collection", "s3Bucket": "kb-bucket"},
            ],
        }

        # Act & Assert
        with pytest.raises(ValueError, match="missing required field"):
            delete_document_from_kb(mock_s3_client, mock_bedrock_agent_client, sample_job, repository)


class TestBulkDeleteWithMultipleFormats:
    """Test bulk deletion with different repository config formats."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client."""
        return MagicMock()

    @pytest.fixture
    def mock_bedrock_agent_client(self):
        """Create mock bedrock-agent client."""
        return MagicMock()

    def test_bulk_delete_with_data_sources_array(self, mock_s3_client, mock_bedrock_agent_client):
        """Test bulk delete with dataSources array."""
        from utilities.bedrock_kb import bulk_delete_documents_from_kb

        # Arrange
        repository = {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {
                "knowledgeBaseId": "KB123",
                "bedrockKnowledgeDatasourceS3Bucket": "kb-bucket",
                "dataSources": [
                    {"id": "DS123", "s3Uri": "s3://kb-bucket/"},
                ],
            },
        }
        s3_paths = ["s3://kb-bucket/doc1.pdf"]

        # Act
        bulk_delete_documents_from_kb(mock_s3_client, mock_bedrock_agent_client, repository, s3_paths)

        # Assert
        mock_bedrock_agent_client.start_ingestion_job.assert_called_once()
        assert mock_bedrock_agent_client.start_ingestion_job.call_args[1]["dataSourceId"] == "DS123"

    def test_bulk_delete_with_data_sources_object_format(self, mock_s3_client, mock_bedrock_agent_client):
        """Test bulk delete with dataSources in object format."""
        from utilities.bedrock_kb import bulk_delete_documents_from_kb

        # Arrange
        class DataSource:
            def __init__(self, id):
                self.id = id

        repository = {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {
                "knowledgeBaseId": "KB123",
                "bedrockKnowledgeDatasourceS3Bucket": "kb-bucket",
                "dataSources": [DataSource("DS123")],
            },
        }
        s3_paths = ["s3://kb-bucket/doc1.pdf"]

        # Act
        bulk_delete_documents_from_kb(mock_s3_client, mock_bedrock_agent_client, repository, s3_paths)

        # Assert
        mock_bedrock_agent_client.start_ingestion_job.assert_called_once()
        assert mock_bedrock_agent_client.start_ingestion_job.call_args[1]["dataSourceId"] == "DS123"

    def test_bulk_delete_with_legacy_datasource_id(self, mock_s3_client, mock_bedrock_agent_client):
        """Test bulk delete with legacy datasource ID."""
        from utilities.bedrock_kb import bulk_delete_documents_from_kb

        # Arrange
        repository = {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {
                "knowledgeBaseId": "KB123",
                "bedrockKnowledgeDatasourceS3Bucket": "kb-bucket",
                "bedrockKnowledgeDatasourceId": "DS-LEGACY",
            },
        }
        s3_paths = ["s3://kb-bucket/doc1.pdf"]

        # Act
        bulk_delete_documents_from_kb(mock_s3_client, mock_bedrock_agent_client, repository, s3_paths)

        # Assert
        mock_bedrock_agent_client.start_ingestion_job.assert_called_once()
        assert mock_bedrock_agent_client.start_ingestion_job.call_args[1]["dataSourceId"] == "DS-LEGACY"

    def test_bulk_delete_missing_kb_id(self, mock_s3_client, mock_bedrock_agent_client):
        """Test bulk delete with missing knowledge base ID."""
        from utilities.bedrock_kb import bulk_delete_documents_from_kb

        # Arrange
        repository = {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {
                "bedrockKnowledgeDatasourceS3Bucket": "kb-bucket",
            },
        }
        s3_paths = ["s3://kb-bucket/doc1.pdf"]

        # Act & Assert
        with pytest.raises(ValueError, match="missing required field"):
            bulk_delete_documents_from_kb(mock_s3_client, mock_bedrock_agent_client, repository, s3_paths)


class TestCreateS3ScanJob:
    """Test creating S3 scan jobs."""

    @pytest.fixture
    def mock_ingestion_job_repo(self):
        """Create mock ingestion job repository."""
        return MagicMock()

    @pytest.fixture
    def mock_ingestion_service(self):
        """Create mock ingestion service."""
        return MagicMock()

    def test_create_s3_scan_job_with_prefix(self, mock_ingestion_job_repo, mock_ingestion_service):
        """Test creating S3 scan job with prefix."""
        from utilities.bedrock_kb import create_s3_scan_job

        # Act
        create_s3_scan_job(
            ingestion_job_repository=mock_ingestion_job_repo,
            ingestion_service=mock_ingestion_service,
            repository_id="test-repo",
            collection_id="test-collection",
            embedding_model="amazon.titan-embed-text-v1",
            s3_bucket="test-bucket",
            s3_prefix="documents/",
        )

        # Assert
        mock_ingestion_job_repo.save.assert_called_once()
        mock_ingestion_service.submit_create_job.assert_called_once()

        saved_job = mock_ingestion_job_repo.save.call_args[0][0]
        assert saved_job.s3_path == "s3://test-bucket/documents/"
        assert saved_job.s3_paths == []
        assert saved_job.job_type == JobActionType.DOCUMENT_BATCH_INGESTION
        assert saved_job.ingestion_type == IngestionType.EXISTING

    def test_create_s3_scan_job_without_prefix(self, mock_ingestion_job_repo, mock_ingestion_service):
        """Test creating S3 scan job without prefix."""
        from utilities.bedrock_kb import create_s3_scan_job

        # Act
        create_s3_scan_job(
            ingestion_job_repository=mock_ingestion_job_repo,
            ingestion_service=mock_ingestion_service,
            repository_id="test-repo",
            collection_id="test-collection",
            embedding_model="amazon.titan-embed-text-v1",
            s3_bucket="test-bucket",
        )

        # Assert
        saved_job = mock_ingestion_job_repo.save.call_args[0][0]
        assert saved_job.s3_path == "s3://test-bucket/"
        assert saved_job.s3_paths == []


class TestS3DocumentDiscoveryService:
    """Test S3 document discovery service."""

    @pytest.fixture
    def mock_s3_client(self):
        """Create mock S3 client."""
        return MagicMock()

    @pytest.fixture
    def mock_bedrock_agent_client(self):
        """Create mock bedrock-agent client."""
        return MagicMock()

    @pytest.fixture
    def mock_rag_document_repo(self):
        """Create mock RAG document repository."""
        return MagicMock()

    @pytest.fixture
    def mock_metadata_generator(self):
        """Create mock metadata generator."""
        mock = MagicMock()
        mock.generate_metadata_json.return_value = {"metadata": "test"}
        return mock

    @pytest.fixture
    def mock_s3_metadata_manager(self):
        """Create mock S3 metadata manager."""
        return MagicMock()

    @pytest.fixture
    def mock_collection_service(self):
        """Create mock collection service."""
        return MagicMock()

    @pytest.fixture
    def mock_vector_store_repo(self):
        """Create mock vector store repository."""
        mock = MagicMock()
        mock.find_repository_by_id.return_value = {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {"knowledgeBaseId": "KB123"},
        }
        return mock

    @pytest.fixture
    def discovery_service(
        self,
        mock_s3_client,
        mock_bedrock_agent_client,
        mock_rag_document_repo,
        mock_metadata_generator,
        mock_s3_metadata_manager,
        mock_collection_service,
        mock_vector_store_repo,
    ):
        """Create S3DocumentDiscoveryService instance."""
        from utilities.bedrock_kb import S3DocumentDiscoveryService

        return S3DocumentDiscoveryService(
            s3_client=mock_s3_client,
            bedrock_agent_client=mock_bedrock_agent_client,
            rag_document_repository=mock_rag_document_repo,
            metadata_generator=mock_metadata_generator,
            s3_metadata_manager=mock_s3_metadata_manager,
            collection_service=mock_collection_service,
            vector_store_repo=mock_vector_store_repo,
        )

    def test_discover_and_ingest_documents_success(self, discovery_service, mock_s3_client, mock_rag_document_repo):
        """Test successful document discovery and ingestion."""
        # Arrange
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "doc1.pdf"},
                {"Key": "doc2.txt"},
            ]
        }
        mock_rag_document_repo.find_by_source.return_value = iter([])

        # Act
        result = discovery_service.discover_and_ingest_documents(
            repository_id="test-repo",
            collection_id="test-collection",
            s3_bucket="test-bucket",
        )

        # Assert
        assert result.discovered == 2
        assert result.successful == 2
        assert result.failed == 0
        assert len(result.document_ids) == 2

    def test_discover_and_ingest_skips_existing_documents(
        self, discovery_service, mock_s3_client, mock_rag_document_repo
    ):
        """Test that existing documents are skipped."""
        # Arrange
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "doc1.pdf"},
            ]
        }
        existing_doc = MagicMock()
        existing_doc.document_id = "existing-doc-id"

        # Mock find_by_source to return existing doc twice (once for check, once for retrieval)
        mock_rag_document_repo.find_by_source.side_effect = [
            iter([existing_doc]),  # First call for _document_exists
            iter([existing_doc]),  # Second call to get the document
        ]

        # Act
        result = discovery_service.discover_and_ingest_documents(
            repository_id="test-repo",
            collection_id="test-collection",
            s3_bucket="test-bucket",
        )

        # Assert
        assert result.discovered == 1
        assert result.successful == 1
        assert result.document_ids[0] == "existing-doc-id"
        # Should not save new document
        mock_rag_document_repo.save.assert_not_called()

    def test_discover_and_ingest_handles_errors(self, discovery_service, mock_s3_client, mock_rag_document_repo):
        """Test handling of errors during document processing."""
        # Arrange
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "doc1.pdf"},
                {"Key": "doc2.pdf"},
            ]
        }
        mock_rag_document_repo.find_by_source.side_effect = [
            iter([]),  # First doc succeeds
            Exception("Database error"),  # Second doc fails
        ]

        # Act
        result = discovery_service.discover_and_ingest_documents(
            repository_id="test-repo",
            collection_id="test-collection",
            s3_bucket="test-bucket",
        )

        # Assert
        assert result.discovered == 2
        assert result.successful == 1
        assert result.failed == 1
        assert len(result.errors) == 1

    def test_discover_and_ingest_empty_bucket(self, discovery_service, mock_s3_client):
        """Test handling of empty bucket."""
        # Arrange
        mock_s3_client.list_objects_v2.return_value = {}

        # Act
        result = discovery_service.discover_and_ingest_documents(
            repository_id="test-repo",
            collection_id="test-collection",
            s3_bucket="test-bucket",
        )

        # Assert
        assert result.discovered == 0
        assert result.successful == 0

    def test_discover_and_ingest_with_prefix(self, discovery_service, mock_s3_client, mock_rag_document_repo):
        """Test discovery with S3 prefix."""
        # Arrange
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "documents/doc1.pdf"},
            ]
        }
        mock_rag_document_repo.find_by_source.return_value = iter([])

        # Act
        result = discovery_service.discover_and_ingest_documents(
            repository_id="test-repo",
            collection_id="test-collection",
            s3_bucket="test-bucket",
            s3_prefix="documents",
        )

        # Assert
        assert result.discovered == 1
        # Verify prefix was used in list_objects_v2 call
        call_args = mock_s3_client.list_objects_v2.call_args[1]
        assert "Prefix" in call_args
        assert call_args["Prefix"] == "documents/"

    def test_scan_s3_bucket_skips_metadata_and_directories(self, discovery_service, mock_s3_client):
        """Test that metadata files and directories are skipped."""
        # Arrange
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "doc1.pdf"},
                {"Key": "doc1.pdf.metadata.json"},
                {"Key": "folder/"},
                {"Key": "doc2.txt"},
            ]
        }

        # Act
        documents, skipped = discovery_service._scan_s3_bucket("test-bucket", "")

        # Assert
        assert len(documents) == 2
        assert skipped == 2
        assert "doc1.pdf" in documents
        assert "doc2.txt" in documents

    def test_discover_and_ingest_handles_collection_fetch_error(
        self, discovery_service, mock_s3_client, mock_rag_document_repo, mock_collection_service
    ):
        """Test handling of collection fetch errors."""
        # Arrange
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "doc1.pdf"},
            ]
        }
        mock_rag_document_repo.find_by_source.return_value = iter([])
        mock_collection_service.get_collection.side_effect = Exception("Collection fetch error")

        # Act
        result = discovery_service.discover_and_ingest_documents(
            repository_id="test-repo",
            collection_id="test-collection",
            s3_bucket="test-bucket",
        )

        # Assert - Should continue despite collection fetch error
        assert result.discovered == 1
        assert result.successful == 1

    def test_discover_and_ingest_handles_metadata_creation_error(
        self, discovery_service, mock_s3_client, mock_rag_document_repo, mock_metadata_generator
    ):
        """Test handling of metadata creation errors."""
        # Arrange
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "doc1.pdf"},
            ]
        }
        mock_rag_document_repo.find_by_source.return_value = iter([])
        mock_metadata_generator.generate_metadata_json.side_effect = Exception("Metadata error")

        # Act
        result = discovery_service.discover_and_ingest_documents(
            repository_id="test-repo",
            collection_id="test-collection",
            s3_bucket="test-bucket",
        )

        # Assert - Should continue despite metadata error
        assert result.discovered == 1
        assert result.successful == 1

    def test_discover_and_ingest_raises_on_critical_error(
        self, discovery_service, mock_s3_client, mock_vector_store_repo
    ):
        """Test that critical errors are raised."""
        # Arrange
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "doc1.pdf"},
            ]
        }
        mock_vector_store_repo.find_repository_by_id.side_effect = Exception("Critical error")

        # Act & Assert
        with pytest.raises(Exception, match="Critical error"):
            discovery_service.discover_and_ingest_documents(
                repository_id="test-repo",
                collection_id="test-collection",
                s3_bucket="test-bucket",
            )

    def test_trigger_kb_sync_missing_kb_id(self, discovery_service, mock_s3_client, mock_rag_document_repo):
        """Test KB sync with missing knowledge base ID."""
        # Arrange
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "doc1.pdf"},
            ]
        }
        mock_rag_document_repo.find_by_source.return_value = iter([])

        # Mock repository without KB ID
        discovery_service.vector_store_repo.find_repository_by_id.return_value = {
            "repositoryId": "test-repo",
            "bedrockKnowledgeBaseConfig": {},
        }

        # Act - Should not raise, just log warning
        result = discovery_service.discover_and_ingest_documents(
            repository_id="test-repo",
            collection_id="test-collection",
            s3_bucket="test-bucket",
        )

        # Assert
        assert result.successful == 1

    def test_trigger_kb_sync_error(
        self, discovery_service, mock_s3_client, mock_rag_document_repo, mock_bedrock_agent_client
    ):
        """Test handling of KB sync errors."""
        # Arrange
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "doc1.pdf"},
            ]
        }
        mock_rag_document_repo.find_by_source.return_value = iter([])
        mock_bedrock_agent_client.start_ingestion_job.side_effect = Exception("Sync error")

        # Act - Should not raise, just log error
        result = discovery_service.discover_and_ingest_documents(
            repository_id="test-repo",
            collection_id="test-collection",
            s3_bucket="test-bucket",
        )

        # Assert
        assert result.successful == 1
