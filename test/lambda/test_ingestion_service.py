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

"""Tests for ingestion service."""

import os
import sys
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))


@pytest.fixture
def setup_env(monkeypatch):
    """Setup environment variables."""
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("LISA_INGESTION_JOB_QUEUE_NAME", "test-queue")
    monkeypatch.setenv("LISA_INGESTION_JOB_DEFINITION_NAME", "test-job-def")


def test_submit_create_job(setup_env):
    """Test submit_create_job submits batch job."""
    from models.domain_objects import IngestionJob
    from repository.ingestion_service import DocumentIngestionService

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="s3://bucket/key",
        embedding_model="model1",
        username="user1",
    )

    with patch("boto3.client") as mock_client:
        mock_batch = Mock()
        mock_batch.submit_job.return_value = {"jobId": "job123"}
        mock_client.return_value = mock_batch

        service = DocumentIngestionService()
        service.submit_create_job(job)

        mock_batch.submit_job.assert_called_once()
        call_args = mock_batch.submit_job.call_args
        assert "document-ingest" in call_args[1]["jobName"]


def test_create_delete_job(setup_env):
    """Test create_delete_job submits delete batch job."""
    from models.domain_objects import IngestionJob
    from repository.ingestion_service import DocumentIngestionService

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="s3://bucket/key",
        embedding_model="model1",
        username="user1",
    )

    with patch("boto3.client") as mock_client:
        mock_batch = Mock()
        mock_batch.submit_job.return_value = {"jobId": "job123"}
        mock_client.return_value = mock_batch

        service = DocumentIngestionService()
        service.create_delete_job(job)

        mock_batch.submit_job.assert_called_once()
        call_args = mock_batch.submit_job.call_args
        assert "document-delete" in call_args[1]["jobName"]


def test_create_ingestion_job_with_collection(setup_env):
    """Test create_ingestion_job with collection and chunking override."""
    from models.domain_objects import FixedChunkingStrategy, IngestDocumentRequest
    from repository.ingestion_service import DocumentIngestionService

    repository = {"repositoryId": "repo1", "embeddingModelId": "repo-model"}

    collection = {
        "collectionId": "col1",
        "embeddingModel": "col-model",
        "allowChunkingOverride": True,
        "chunkingStrategy": FixedChunkingStrategy(size=500, overlap=50),
    }

    request = IngestDocumentRequest(
        keys=["key1"],
        collectionId="col1",
        chunkingStrategy={"type": "FIXED", "size": 1000, "overlap": 100},
    )

    query_params = {}

    service = DocumentIngestionService()

    with patch.object(service, "create_ingestion_job") as mock_create:
        from models.domain_objects import IngestionJob

        mock_job = IngestionJob(
            repository_id="repo1",
            collection_id="col1",
            s3_path="s3://bucket/key",
            embedding_model="col-model",
            username="user1",
            chunk_strategy=FixedChunkingStrategy(size=1000, overlap=100),
        )
        mock_create.return_value = mock_job

        job = service.create_ingestion_job(repository, collection, request, query_params, "s3://bucket/key", "user1")

        assert job.collection_id == "col1"
        assert job.embedding_model == "col-model"
        assert job.chunk_strategy.size == 1000


def test_create_ingestion_job_without_collection(setup_env):
    """Test create_ingestion_job without collection uses repository defaults."""
    from models.domain_objects import FixedChunkingStrategy, IngestDocumentRequest
    from repository.ingestion_service import DocumentIngestionService

    repository = {"repositoryId": "repo1", "embeddingModelId": "repo-model"}

    request = IngestDocumentRequest(keys=["key1"])

    query_params = {"chunkSize": 800, "chunkOverlap": 80}

    service = DocumentIngestionService()

    with patch.object(service, "create_ingestion_job") as mock_create:
        from models.domain_objects import IngestionJob

        mock_job = IngestionJob(
            repository_id="repo1",
            collection_id="repo-model",
            s3_path="s3://bucket/key",
            embedding_model="repo-model",
            username="user1",
            chunk_strategy=FixedChunkingStrategy(size=800, overlap=80),
        )
        mock_create.return_value = mock_job

        job = service.create_ingestion_job(repository, None, request, query_params, "s3://bucket/key", "user1")

        assert job.collection_id == "repo-model"
        assert job.embedding_model == "repo-model"
        assert job.chunk_strategy.size == 800


def test_create_ingestion_job_with_embedding_model_in_request(setup_env):
    """Test create_ingestion_job with embedding model in request."""
    from models.domain_objects import IngestDocumentRequest
    from repository.ingestion_service import DocumentIngestionService

    repository = {"repositoryId": "repo1", "embeddingModelId": "repo-model"}

    request = IngestDocumentRequest(keys=["key1"], embeddingModel={"modelName": "request-model"})

    query_params = {}

    service = DocumentIngestionService()

    with patch.object(service, "create_ingestion_job") as mock_create:
        from models.domain_objects import FixedChunkingStrategy, IngestionJob

        mock_job = IngestionJob(
            repository_id="repo1",
            collection_id="request-model",
            s3_path="s3://bucket/key",
            embedding_model="repo-model",
            username="user1",
            chunk_strategy=FixedChunkingStrategy(size=1000, overlap=100),
        )
        mock_create.return_value = mock_job

        job = service.create_ingestion_job(repository, None, request, query_params, "s3://bucket/key", "user1")

        assert job.collection_id == "request-model"


def test_create_ingestion_job_invalid_chunking_strategy(setup_env):
    """Test create_ingestion_job handles invalid chunking strategy."""
    from models.domain_objects import IngestDocumentRequest
    from repository.ingestion_service import DocumentIngestionService

    repository = {"repositoryId": "repo1", "embeddingModelId": "repo-model"}

    collection = {
        "collectionId": "col1",
        "embeddingModel": "col-model",
        "allowChunkingOverride": True,
        "chunkingStrategy": {"type": "FIXED", "size": 500, "overlap": 50},
    }

    request = IngestDocumentRequest(
        keys=["key1"],
        collectionId="col1",
        chunkingStrategy={"type": "FIXED", "size": "invalid"},  # Invalid size
    )

    query_params = {}

    service = DocumentIngestionService()

    with patch.object(service, "create_ingestion_job") as mock_create:
        from models.domain_objects import FixedChunkingStrategy, IngestionJob

        mock_job = IngestionJob(
            repository_id="repo1",
            collection_id="col1",
            s3_path="s3://bucket/key",
            embedding_model="col-model",
            username="user1",
            chunk_strategy=FixedChunkingStrategy(size=500, overlap=50),
        )
        mock_create.return_value = mock_job

        job = service.create_ingestion_job(repository, collection, request, query_params, "s3://bucket/key", "user1")

        # Should fall back to collection's chunking strategy
        assert job.chunk_strategy.size == 500
