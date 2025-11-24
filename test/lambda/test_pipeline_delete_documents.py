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

"""Tests for pipeline delete documents."""

import os
import sys
from unittest import mock
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))


@pytest.fixture
def setup_env(monkeypatch):
    """Setup environment variables."""
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("RAG_DOCUMENT_TABLE", "test-doc-table")
    monkeypatch.setenv("RAG_SUB_DOCUMENT_TABLE", "test-subdoc-table")
    monkeypatch.setenv("LISA_INGESTION_JOB_TABLE_NAME", "test-job-table")
    monkeypatch.setenv("LISA_INGESTION_JOB_QUEUE_NAME", "test-queue")
    monkeypatch.setenv("LISA_INGESTION_JOB_DEFINITION_NAME", "test-job-def")
    monkeypatch.setenv("LISA_RAG_VECTOR_STORE_TABLE", "test-vector-store-table")


def test_drop_opensearch_index(setup_env):
    """Test drop_opensearch_index delegates to service layer."""
    from repository.pipeline_delete_documents import drop_opensearch_index

    mock_service = Mock()

    with patch("repository.pipeline_delete_documents.vs_repo") as mock_vs_repo, patch(
        "repository.pipeline_delete_documents.RepositoryServiceFactory"
    ) as mock_factory:
        mock_vs_repo.find_repository_by_id.return_value = {"repositoryId": "repo1", "type": "opensearch"}
        mock_factory.create_service.return_value = mock_service

        drop_opensearch_index("repo1", "col1")

        mock_service.delete_collection.assert_called_once_with("col1", s3_client=mock.ANY)


def test_drop_opensearch_index_not_exists(setup_env):
    """Test drop_opensearch_index delegates to service layer even when index doesn't exist."""
    from repository.pipeline_delete_documents import drop_opensearch_index

    mock_service = Mock()

    with patch("repository.pipeline_delete_documents.vs_repo") as mock_vs_repo, patch(
        "repository.pipeline_delete_documents.RepositoryServiceFactory"
    ) as mock_factory:
        mock_vs_repo.find_repository_by_id.return_value = {"repositoryId": "repo1", "type": "opensearch"}
        mock_factory.create_service.return_value = mock_service

        drop_opensearch_index("repo1", "col1")

        mock_service.delete_collection.assert_called_once_with("col1", s3_client=mock.ANY)


def test_drop_pgvector_collection(setup_env):
    """Test drop_pgvector_collection delegates to service layer."""
    from repository.pipeline_delete_documents import drop_pgvector_collection

    mock_service = Mock()

    with patch("repository.pipeline_delete_documents.vs_repo") as mock_vs_repo, patch(
        "repository.pipeline_delete_documents.RepositoryServiceFactory"
    ) as mock_factory:
        mock_vs_repo.find_repository_by_id.return_value = {"repositoryId": "repo1", "type": "pgvector"}
        mock_factory.create_service.return_value = mock_service

        drop_pgvector_collection("repo1", "col1")

        mock_service.delete_collection.assert_called_once_with("col1", s3_client=mock.ANY)


def test_pipeline_delete_collection_opensearch(setup_env):
    """Test pipeline_delete_collection with OpenSearch repository."""
    from models.domain_objects import IngestionJob, IngestionStatus, JobActionType
    from utilities.repository_types import RepositoryType

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="",
        embedding_model="model1",
        username="user1",
        job_type=JobActionType.COLLECTION_DELETION,
    )

    with patch("repository.pipeline_delete_documents.vs_repo") as mock_vs_repo, patch(
        "repository.pipeline_delete_documents.drop_opensearch_index"
    ) as mock_drop, patch("repository.pipeline_delete_documents.rag_document_repository") as mock_doc_repo, patch(
        "repository.pipeline_delete_documents.collection_repo"
    ), patch(
        "repository.pipeline_delete_documents.ingestion_job_repository"
    ) as mock_job_repo:

        mock_vs_repo.find_repository_by_id.return_value = {"type": RepositoryType.OPENSEARCH}

        from repository.pipeline_delete_documents import pipeline_delete_collection

        pipeline_delete_collection(job)

        mock_drop.assert_called_once_with("repo1", "col1")
        mock_doc_repo.delete_all.assert_called_once_with("repo1", "col1")
        mock_job_repo.update_status.assert_called_with(job, IngestionStatus.DELETE_COMPLETED)


def test_pipeline_delete_collection_bedrock_kb(setup_env):
    """Test pipeline_delete_collection with Bedrock KB repository."""
    from models.domain_objects import IngestionJob, JobActionType
    from utilities.repository_types import RepositoryType

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="",
        embedding_model="model1",
        username="user1",
        job_type=JobActionType.COLLECTION_DELETION,
    )

    with patch("repository.pipeline_delete_documents.vs_repo") as mock_vs_repo, patch(
        "repository.pipeline_delete_documents.boto3"
    ) as mock_boto3, patch("repository.pipeline_delete_documents.rag_document_repository") as mock_doc_repo, patch(
        "repository.pipeline_delete_documents.collection_repo"
    ), patch(
        "repository.pipeline_delete_documents.ingestion_job_repository"
    ), patch(
        "repository.pipeline_delete_documents.bulk_delete_documents_from_kb"
    ) as mock_bulk_delete:

        mock_vs_repo.find_repository_by_id.return_value = {"type": RepositoryType.BEDROCK_KB}

        mock_dynamodb = Mock()
        mock_table = Mock()
        mock_table.query.return_value = {
            "Items": [
                {"pk": "repo1#col1", "source": "s3://bucket/key1", "ingestion_type": "manual"},
                {"pk": "repo1#col1", "source": "s3://bucket/key2", "ingestion_type": "auto"},
            ]
        }
        mock_dynamodb.Table.return_value = mock_table
        mock_boto3.resource.return_value = mock_dynamodb

        from repository.pipeline_delete_documents import pipeline_delete_collection

        pipeline_delete_collection(job)

        mock_bulk_delete.assert_called_once()
        mock_doc_repo.delete_all.assert_called_once()


def test_pipeline_delete_collection_failure(setup_env):
    """Test pipeline_delete_collection handles failures."""
    from models.domain_objects import IngestionJob, IngestionStatus, JobActionType
    from utilities.repository_types import RepositoryType

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="",
        embedding_model="model1",
        username="user1",
        job_type=JobActionType.COLLECTION_DELETION,
    )

    with patch("repository.pipeline_delete_documents.vs_repo") as mock_vs_repo, patch(
        "repository.pipeline_delete_documents.rag_document_repository"
    ) as mock_doc_repo, patch("repository.pipeline_delete_documents.collection_repo") as mock_coll_repo, patch(
        "repository.pipeline_delete_documents.ingestion_job_repository"
    ) as mock_job_repo:

        mock_vs_repo.find_repository_by_id.return_value = {"type": RepositoryType.OPENSEARCH}
        mock_doc_repo.delete_all.side_effect = Exception("Delete failed")

        from repository.pipeline_delete_documents import pipeline_delete_collection

        with pytest.raises(Exception):
            pipeline_delete_collection(job)

        mock_job_repo.update_status.assert_called_with(job, IngestionStatus.DELETE_FAILED)
        mock_coll_repo.update.assert_called()


def test_pipeline_delete_document(setup_env):
    """Test pipeline_delete_document deletes single document."""
    from models.domain_objects import IngestionJob, IngestionStatus, RagDocument
    from utilities.repository_types import RepositoryType

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="s3://bucket/key",
        embedding_model="model1",
        username="user1",
        document_id="doc1",
    )

    from models.domain_objects import FixedChunkingStrategy

    rag_doc = RagDocument(
        repository_id="repo1",
        collection_id="col1",
        document_id="doc1",
        document_name="test.txt",
        source="s3://bucket/key",
        subdocs=["sub1", "sub2"],
        username="user1",
        chunk_strategy=FixedChunkingStrategy(size=1000, overlap=100),
    )

    with patch("repository.pipeline_delete_documents.rag_document_repository") as mock_doc_repo, patch(
        "repository.pipeline_delete_documents.vs_repo"
    ) as mock_vs_repo, patch("repository.pipeline_delete_documents.remove_document_from_vectorstore"), patch(
        "repository.pipeline_delete_documents.ingestion_job_repository"
    ) as mock_job_repo:

        mock_doc_repo.find_by_id.return_value = rag_doc
        mock_vs_repo.find_repository_by_id.return_value = {"type": RepositoryType.OPENSEARCH}

        from repository.pipeline_delete_documents import pipeline_delete_document

        pipeline_delete_document(job)

        mock_doc_repo.delete_by_id.assert_called_once_with("doc1")
        mock_job_repo.update_status.assert_called_with(job, IngestionStatus.DELETE_COMPLETED)


def test_pipeline_delete_document_not_found(setup_env):
    """Test pipeline_delete_document when document not found."""
    from models.domain_objects import IngestionJob, IngestionStatus

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="s3://bucket/key",
        embedding_model="model1",
        username="user1",
        document_id="doc1",
    )

    with patch("repository.pipeline_delete_documents.rag_document_repository") as mock_doc_repo, patch(
        "repository.pipeline_delete_documents.ingestion_job_repository"
    ) as mock_job_repo:

        mock_doc_repo.find_by_id.return_value = None

        from repository.pipeline_delete_documents import pipeline_delete_document

        pipeline_delete_document(job)

        mock_job_repo.update_status.assert_called_with(job, IngestionStatus.DELETE_COMPLETED)


def test_handle_pipeline_delete_event(setup_env):
    """Test handle_pipeline_delete_event processes delete event."""
    event = {
        "detail": {
            "bucket": "test-bucket",
            "key": "test-key",
            "repositoryId": "repo1",
            "pipelineConfig": {"embeddingModel": "model1"},
        }
    }

    with patch("repository.pipeline_delete_documents.rag_document_repository") as mock_doc_repo, patch(
        "repository.pipeline_delete_documents.ingestion_job_repository"
    ) as mock_job_repo, patch("repository.pipeline_delete_documents.ingestion_service") as mock_service:

        from models.domain_objects import FixedChunkingStrategy, RagDocument

        rag_doc = RagDocument(
            repository_id="repo1",
            collection_id="model1",
            document_id="doc1",
            document_name="test.txt",
            source="s3://test-bucket/test-key",
            subdocs=[],
            username="user1",
            chunk_strategy=FixedChunkingStrategy(size=1000, overlap=100),
        )

        mock_doc_repo.find_by_source.return_value = [rag_doc]
        mock_job_repo.find_by_document.return_value = None

        from repository.pipeline_delete_documents import handle_pipeline_delete_event

        handle_pipeline_delete_event(event, None)

        mock_service.create_delete_job.assert_called_once()


def test_handle_pipeline_delete_event_no_pipeline_config(setup_env):
    """Test handle_pipeline_delete_event skips when no pipeline config."""
    event = {"detail": {"bucket": "test-bucket", "key": "test-key", "repositoryId": "repo1"}}

    from repository.pipeline_delete_documents import handle_pipeline_delete_event

    # Should return without error
    handle_pipeline_delete_event(event, None)


def test_pipeline_delete_routes_to_collection_deletion(setup_env):
    """Test pipeline_delete routes to collection deletion."""
    from models.domain_objects import IngestionJob, JobActionType

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="",
        embedding_model="model1",
        username="user1",
        job_type=JobActionType.COLLECTION_DELETION,
    )

    with patch("repository.pipeline_delete_documents.pipeline_delete_collection") as mock_delete_collection:
        from repository.pipeline_delete_documents import pipeline_delete

        pipeline_delete(job)

        mock_delete_collection.assert_called_once_with(job)


def test_pipeline_delete_routes_to_document_deletion(setup_env):
    """Test pipeline_delete routes to document deletion."""
    from models.domain_objects import IngestionJob

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="s3://bucket/key",
        embedding_model="model1",
        username="user1",
    )

    with patch("repository.pipeline_delete_documents.pipeline_delete_document") as mock_delete_document:
        from repository.pipeline_delete_documents import pipeline_delete

        pipeline_delete(job)

        mock_delete_document.assert_called_once_with(job)


def test_pipeline_delete_documents_batch(setup_env):
    """Test pipeline_delete_documents processes batch deletion."""
    from models.domain_objects import FixedChunkingStrategy, IngestionJob, IngestionStatus, JobActionType, RagDocument
    from utilities.repository_types import RepositoryType

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="",
        embedding_model="model1",
        username="user1",
        job_type=JobActionType.DOCUMENT_BATCH_DELETION,
        document_ids=["doc1", "doc2", "doc3"],
    )

    rag_docs = [
        RagDocument(
            repository_id="repo1",
            collection_id="col1",
            document_id=f"doc{i}",
            document_name=f"test{i}.txt",
            source=f"s3://bucket/key{i}",
            subdocs=[f"sub{i}"],
            username="user1",
            chunk_strategy=FixedChunkingStrategy(size=1000, overlap=100),
        )
        for i in range(1, 4)
    ]

    with patch("repository.pipeline_delete_documents.rag_document_repository") as mock_doc_repo, patch(
        "repository.pipeline_delete_documents.vs_repo"
    ) as mock_vs_repo, patch("repository.pipeline_delete_documents.remove_document_from_vectorstore"), patch(
        "repository.pipeline_delete_documents.ingestion_job_repository"
    ) as mock_job_repo:

        mock_doc_repo.find_by_id.side_effect = rag_docs
        mock_vs_repo.find_repository_by_id.return_value = {"type": RepositoryType.OPENSEARCH}

        from repository.pipeline_delete_documents import pipeline_delete_documents

        pipeline_delete_documents(job)

        assert mock_doc_repo.delete_by_id.call_count == 3
        mock_job_repo.update_status.assert_called_with(job, IngestionStatus.DELETE_COMPLETED)


def test_pipeline_delete_documents_batch_with_failures(setup_env):
    """Test pipeline_delete_documents handles partial failures."""
    from models.domain_objects import FixedChunkingStrategy, IngestionJob, IngestionStatus, JobActionType, RagDocument
    from utilities.repository_types import RepositoryType

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="",
        embedding_model="model1",
        username="user1",
        job_type=JobActionType.DOCUMENT_BATCH_DELETION,
        document_ids=["doc1", "doc2", "doc3"],
    )

    rag_doc1 = RagDocument(
        repository_id="repo1",
        collection_id="col1",
        document_id="doc1",
        document_name="test1.txt",
        source="s3://bucket/key1",
        subdocs=["sub1"],
        username="user1",
        chunk_strategy=FixedChunkingStrategy(size=1000, overlap=100),
    )

    with patch("repository.pipeline_delete_documents.rag_document_repository") as mock_doc_repo, patch(
        "repository.pipeline_delete_documents.vs_repo"
    ) as mock_vs_repo, patch("repository.pipeline_delete_documents.remove_document_from_vectorstore"), patch(
        "repository.pipeline_delete_documents.ingestion_job_repository"
    ) as mock_job_repo:

        # First succeeds, second fails, third succeeds
        mock_doc_repo.find_by_id.side_effect = [rag_doc1, Exception("Delete failed"), rag_doc1]
        mock_vs_repo.find_repository_by_id.return_value = {"type": RepositoryType.OPENSEARCH}

        from repository.pipeline_delete_documents import pipeline_delete_documents

        pipeline_delete_documents(job)

        mock_job_repo.update_status.assert_called_with(job, IngestionStatus.DELETE_FAILED)


def test_pipeline_delete_documents_batch_exceeds_limit(setup_env):
    """Test pipeline_delete_documents rejects batch over 100 documents."""
    from models.domain_objects import IngestionJob, JobActionType

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="",
        embedding_model="model1",
        username="user1",
        job_type=JobActionType.DOCUMENT_BATCH_DELETION,
        document_ids=[f"doc{i}" for i in range(101)],
    )

    with patch("repository.pipeline_delete_documents.ingestion_job_repository") as mock_job_repo:
        from repository.pipeline_delete_documents import pipeline_delete_documents

        with pytest.raises(Exception):
            pipeline_delete_documents(job)

        mock_job_repo.update_status.assert_called()


def test_pipeline_delete_routes_to_batch_deletion(setup_env):
    """Test pipeline_delete routes to batch document deletion."""
    from models.domain_objects import IngestionJob, JobActionType

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="",
        embedding_model="model1",
        username="user1",
        job_type=JobActionType.DOCUMENT_BATCH_DELETION,
        document_ids=["doc1", "doc2"],
    )

    with patch("repository.pipeline_delete_documents.pipeline_delete_documents") as mock_delete_documents:
        from repository.pipeline_delete_documents import pipeline_delete

        pipeline_delete(job)

        mock_delete_documents.assert_called_once_with(job)
