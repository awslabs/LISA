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

"""Tests for pipeline ingest documents."""

import os
import sys
from datetime import datetime, timedelta, timezone
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


def test_extract_chunk_strategy_new_format(setup_env):
    """Test extract_chunk_strategy with new chunkingStrategy object format."""
    from repository.pipeline_ingest_documents import extract_chunk_strategy

    pipeline_config = {"chunkingStrategy": {"type": "fixed", "size": 1000, "overlap": 100}}

    strategy = extract_chunk_strategy(pipeline_config)

    assert strategy.size == 1000
    assert strategy.overlap == 100


def test_extract_chunk_strategy_legacy_format(setup_env):
    """Test extract_chunk_strategy with legacy flat fields."""
    from repository.pipeline_ingest_documents import extract_chunk_strategy

    pipeline_config = {"chunkSize": 800, "chunkOverlap": 80}

    strategy = extract_chunk_strategy(pipeline_config)

    assert strategy.size == 800
    assert strategy.overlap == 80


def test_extract_chunk_strategy_defaults(setup_env):
    """Test extract_chunk_strategy uses defaults when no config."""
    from repository.pipeline_ingest_documents import extract_chunk_strategy

    pipeline_config = {}

    strategy = extract_chunk_strategy(pipeline_config)

    assert strategy.size == 512
    assert strategy.overlap == 51


def test_extract_chunk_strategy_unsupported_type(setup_env):
    """Test extract_chunk_strategy raises error for unsupported type."""
    from repository.pipeline_ingest_documents import extract_chunk_strategy

    pipeline_config = {"chunkingStrategy": {"type": "semantic", "size": 1000}}

    with pytest.raises(ValueError, match="Unsupported chunking strategy"):
        extract_chunk_strategy(pipeline_config)


def test_batch_texts(setup_env):
    """Test batch_texts splits texts into batches."""
    from repository.pipeline_ingest_documents import batch_texts

    texts = [f"text{i}" for i in range(1200)]
    metadatas = [{"id": i} for i in range(1200)]

    batches = batch_texts(texts, metadatas, batch_size=500)

    assert len(batches) == 3
    assert len(batches[0][0]) == 500
    assert len(batches[1][0]) == 500
    assert len(batches[2][0]) == 200


def test_prepare_chunks(setup_env):
    """Test prepare_chunks extracts texts and metadatas."""
    from repository.pipeline_ingest_documents import prepare_chunks

    mock_doc1 = Mock()
    mock_doc1.page_content = "content1"
    mock_doc1.metadata = {"key": "value1"}

    mock_doc2 = Mock()
    mock_doc2.page_content = "content2"
    mock_doc2.metadata = {"key": "value2"}

    texts, metadatas = prepare_chunks([mock_doc1, mock_doc2], "repo1", "col1")

    assert texts == ["content1", "content2"]
    assert len(metadatas) == 2


def test_store_chunks_in_vectorstore(setup_env):
    """Test store_chunks_in_vectorstore stores chunks in batches."""
    from repository.pipeline_ingest_documents import store_chunks_in_vectorstore

    texts = [f"text{i}" for i in range(1200)]
    metadatas = [{"id": i} for i in range(1200)]

    mock_vs = Mock()
    mock_vs.add_texts.return_value = ["id1", "id2"]

    mock_service = Mock()
    mock_service.get_vector_store_client.return_value = mock_vs

    with patch("repository.pipeline_ingest_documents.RagEmbeddings"), patch(
        "repository.pipeline_ingest_documents.VectorStoreRepository"
    ) as mock_vs_repo, patch("repository.pipeline_ingest_documents.RepositoryServiceFactory") as mock_factory:
        mock_vs_repo.return_value.find_repository_by_id.return_value = {"repositoryId": "repo1", "type": "opensearch"}
        mock_factory.create_service.return_value = mock_service

        ids = store_chunks_in_vectorstore(texts, metadatas, "repo1", "col1", "model1")

        assert len(ids) > 0
        assert mock_vs.add_texts.call_count == 5  # 1200 texts / 256 batch size


def test_store_chunks_in_vectorstore_failure(setup_env):
    """Test store_chunks_in_vectorstore raises error on failure."""
    from repository.pipeline_ingest_documents import store_chunks_in_vectorstore

    texts = ["text1"]
    metadatas = [{"id": 1}]

    mock_vs = Mock()
    mock_vs.add_texts.return_value = None

    mock_service = Mock()
    mock_service.get_vector_store_client.return_value = mock_vs

    with patch("repository.pipeline_ingest_documents.RagEmbeddings"), patch(
        "repository.pipeline_ingest_documents.VectorStoreRepository"
    ) as mock_vs_repo, patch("repository.pipeline_ingest_documents.RepositoryServiceFactory") as mock_factory:
        mock_vs_repo.return_value.find_repository_by_id.return_value = {"repositoryId": "repo1", "type": "opensearch"}
        mock_factory.create_service.return_value = mock_service

        with pytest.raises(Exception, match="Failed to store documents"):
            store_chunks_in_vectorstore(texts, metadatas, "repo1", "col1", "model1")


def test_pipeline_ingest_bedrock_kb(setup_env):
    """Test pipeline_ingest with Bedrock KB repository - only tracks documents."""
    from models.domain_objects import IngestionJob, IngestionStatus, NoneChunkingStrategy
    from utilities.repository_types import RepositoryType

    job = IngestionJob(
        repository_id="repo1",
        collection_id="ds-123",  # Data source ID
        s3_path="s3://kb-bucket/document.pdf",
        embedding_model="model1",
        username="system",
        chunk_strategy=NoneChunkingStrategy(),
    )

    bedrock_kb_repo = {
        "type": RepositoryType.BEDROCK_KB,
        "bedrockKnowledgeBaseConfig": {
            "bedrockKnowledgeDatasourceS3Bucket": "kb-bucket",
            "bedrockKnowledgeDatasourceId": "ds-123",
        },
    }

    with patch("repository.pipeline_ingest_documents.vs_repo") as mock_vs_repo, patch(
        "repository.pipeline_ingest_documents.rag_document_repository"
    ) as mock_doc_repo, patch("repository.pipeline_ingest_documents.ingestion_job_repository") as mock_job_repo:

        mock_vs_repo.find_repository_by_id.return_value = bedrock_kb_repo
        mock_doc_repo.find_by_source.return_value = []

        from repository.pipeline_ingest_documents import pipeline_ingest

        pipeline_ingest(job)

        # For Bedrock KB, we only track the document, no chunking or embedding
        mock_doc_repo.save.assert_called_once()
        mock_job_repo.save.assert_called()
        assert job.status == IngestionStatus.INGESTION_COMPLETED


def test_pipeline_ingest_bedrock_kb_copy_from_lisa_bucket(setup_env):
    """Test pipeline_ingest with Bedrock KB repository - copies from LISA bucket to KB bucket."""
    from models.domain_objects import IngestionJob, IngestionStatus, NoneChunkingStrategy
    from utilities.repository_types import RepositoryType

    job = IngestionJob(
        repository_id="repo1",
        collection_id="ds-123",  # Data source ID
        s3_path="s3://lisa-bucket/document.pdf",  # Document in LISA bucket
        embedding_model="model1",
        username="user1",
        chunk_strategy=NoneChunkingStrategy(),
    )

    bedrock_kb_repo = {
        "type": RepositoryType.BEDROCK_KB,
        "bedrockKnowledgeBaseConfig": {
            "bedrockKnowledgeDatasourceS3Bucket": "kb-bucket",
            "bedrockKnowledgeDatasourceId": "ds-123",
            "bedrockKnowledgeBaseId": "kb-123",
        },
    }

    with patch("repository.pipeline_ingest_documents.vs_repo") as mock_vs_repo, patch(
        "repository.pipeline_ingest_documents.rag_document_repository"
    ) as mock_doc_repo, patch("repository.pipeline_ingest_documents.ingestion_job_repository") as mock_job_repo, patch(
        "repository.pipeline_ingest_documents.s3"
    ) as mock_s3, patch(
        "repository.pipeline_ingest_documents.bedrock_agent"
    ) as mock_bedrock_agent:

        mock_vs_repo.find_repository_by_id.return_value = bedrock_kb_repo
        mock_doc_repo.find_by_source.return_value = []

        from repository.pipeline_ingest_documents import pipeline_ingest

        pipeline_ingest(job)

        # Verify document was copied from LISA bucket to KB bucket
        mock_s3.copy_object.assert_called_once_with(
            CopySource={"Bucket": "lisa-bucket", "Key": "document.pdf"},
            Bucket="kb-bucket",
            Key="document.pdf",
        )

        # Verify source file was deleted from LISA bucket
        mock_s3.delete_object.assert_called_once_with(Bucket="lisa-bucket", Key="document.pdf")

        # Verify KB ingestion was triggered
        mock_bedrock_agent.start_ingestion_job.assert_called_once_with(knowledgeBaseId="kb-123", dataSourceId="ds-123")

        # Verify document was tracked with KB bucket path
        mock_doc_repo.save.assert_called_once()
        saved_doc = mock_doc_repo.save.call_args[0][0]
        assert saved_doc.source == "s3://kb-bucket/document.pdf"

        mock_job_repo.save.assert_called()
        assert job.status == IngestionStatus.INGESTION_COMPLETED


def test_pipeline_ingest_with_previous_document(setup_env):
    """Test pipeline_ingest removes previous document version."""
    from models.domain_objects import FixedChunkingStrategy, IngestionJob, RagDocument
    from utilities.repository_types import RepositoryType

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="s3://bucket/key",
        embedding_model="model1",
        username="user1",
        chunk_strategy=FixedChunkingStrategy(size=1000, overlap=100),
    )

    prev_doc = RagDocument(
        repository_id="repo1",
        collection_id="col1",
        document_id="prev-doc",
        document_name="test.txt",
        source="s3://bucket/key",
        subdocs=["sub1"],
        username="user1",
        chunk_strategy=FixedChunkingStrategy(size=1000, overlap=100),
    )

    prev_job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="s3://bucket/key",
        embedding_model="model1",
        username="user1",
        document_id="prev-doc",
    )

    with patch("repository.pipeline_ingest_documents.vs_repo") as mock_vs_repo, patch(
        "repository.pipeline_ingest_documents.generate_chunks"
    ) as mock_chunks, patch("repository.pipeline_ingest_documents.prepare_chunks") as mock_prepare, patch(
        "repository.pipeline_ingest_documents.store_chunks_in_vectorstore"
    ) as mock_store, patch(
        "repository.pipeline_ingest_documents.rag_document_repository"
    ) as mock_doc_repo, patch(
        "repository.pipeline_ingest_documents.ingestion_job_repository"
    ) as mock_job_repo, patch(
        "repository.pipeline_ingest_documents.remove_document_from_vectorstore"
    ):

        mock_vs_repo.find_repository_by_id.return_value = {"type": RepositoryType.OPENSEARCH}
        mock_chunks.return_value = [Mock(page_content="text", metadata={})]
        mock_prepare.return_value = (["text"], [{"key": "value"}])
        mock_store.return_value = ["id1"]
        mock_doc_repo.find_by_source.return_value = [prev_doc]
        mock_job_repo.find_by_document.return_value = prev_job

        from repository.pipeline_ingest_documents import pipeline_ingest

        pipeline_ingest(job)

        mock_doc_repo.delete_by_id.assert_called_once_with("prev-doc")
        assert mock_job_repo.update_status.call_count >= 2  # DELETE_IN_PROGRESS and DELETE_COMPLETED


def test_handle_pipeline_ingest_event(setup_env):
    """Test handle_pipeline_ingest_event processes ingest event."""
    event = {
        "detail": {
            "bucket": "test-bucket",
            "key": "test-key",
            "repositoryId": "repo1",
            "pipelineConfig": {"embeddingModel": "model1", "chunkSize": 1000, "chunkOverlap": 100},
        },
        "requestContext": {"authorizer": {"username": "user1"}},
    }

    with patch("repository.pipeline_ingest_documents.vs_repo") as mock_vs_repo, patch(
        "repository.pipeline_ingest_documents.collection_service"
    ) as mock_coll_service, patch(
        "repository.pipeline_ingest_documents.ingestion_job_repository"
    ) as mock_job_repo, patch(
        "repository.pipeline_ingest_documents.ingestion_service"
    ) as mock_service:

        mock_vs_repo.find_repository_by_id.return_value = {"repositoryId": "repo1"}
        mock_coll_service.get_collection_metadata.return_value = {}

        from repository.pipeline_ingest_documents import handle_pipeline_ingest_event

        handle_pipeline_ingest_event(event, None)

        mock_job_repo.save.assert_called_once()
        mock_service.submit_create_job.assert_called_once()


def test_handle_pipline_ingest_schedule(setup_env):
    """Test handle_pipline_ingest_schedule lists and ingests modified files."""
    event = {
        "detail": {
            "bucket": "test-bucket",
            "prefix": "test-prefix/",
            "repositoryId": "repo1",
            "pipelineConfig": {"embeddingModel": "model1", "chunkSize": 1000, "chunkOverlap": 100},
        },
        "requestContext": {"authorizer": {"username": "user1"}},
    }

    now = datetime.now(timezone.utc)
    recent = now - timedelta(hours=12)

    with patch("repository.pipeline_ingest_documents.s3") as mock_s3, patch(
        "repository.pipeline_ingest_documents.vs_repo"
    ) as mock_vs_repo, patch("repository.pipeline_ingest_documents.collection_service") as mock_coll_service, patch(
        "repository.pipeline_ingest_documents.ingestion_job_repository"
    ) as mock_job_repo, patch(
        "repository.pipeline_ingest_documents.ingestion_service"
    ) as mock_service:

        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [
            {
                "Contents": [
                    {"Key": "test-prefix/file1.txt", "LastModified": recent},
                    {"Key": "test-prefix/file2.txt", "LastModified": now - timedelta(days=2)},
                ]
            }
        ]
        mock_s3.get_paginator.return_value = mock_paginator
        mock_vs_repo.find_repository_by_id.return_value = {"repositoryId": "repo1"}
        mock_coll_service.get_collection_metadata.return_value = {}

        from repository.pipeline_ingest_documents import handle_pipline_ingest_schedule

        handle_pipline_ingest_schedule(event, None)

        # Only file1.txt should be ingested (modified in last 24 hours)
        assert mock_job_repo.save.call_count == 1
        assert mock_service.submit_create_job.call_count == 1


def test_handle_pipline_ingest_schedule_no_contents(setup_env):
    """Test handle_pipline_ingest_schedule handles empty bucket."""
    event = {
        "detail": {
            "bucket": "test-bucket",
            "prefix": "test-prefix/",
            "repositoryId": "repo1",
            "pipelineConfig": {"embeddingModel": "model1"},
        },
        "requestContext": {"authorizer": {"username": "user1"}},
    }

    with patch("repository.pipeline_ingest_documents.s3") as mock_s3, patch(
        "repository.pipeline_ingest_documents.vs_repo"
    ) as mock_vs_repo, patch("repository.pipeline_ingest_documents.collection_service") as mock_coll_service:

        mock_paginator = Mock()
        mock_paginator.paginate.return_value = [{}]  # No Contents key
        mock_s3.get_paginator.return_value = mock_paginator
        mock_vs_repo.find_repository_by_id.return_value = {"repositoryId": "repo1"}
        mock_coll_service.get_collection_metadata.return_value = {}

        from repository.pipeline_ingest_documents import handle_pipline_ingest_schedule

        # Should not raise error
        handle_pipline_ingest_schedule(event, None)


def test_remove_document_from_vectorstore(setup_env):
    """Test remove_document_from_vectorstore deletes from vector store."""
    from models.domain_objects import FixedChunkingStrategy, RagDocument

    doc = RagDocument(
        repository_id="repo1",
        collection_id="col1",
        document_id="doc1",
        document_name="test.txt",
        source="s3://bucket/key",
        subdocs=["sub1", "sub2"],
        username="user1",
        chunk_strategy=FixedChunkingStrategy(size=1000, overlap=100),
    )

    mock_vs = Mock()
    mock_service = Mock()
    mock_service.get_vector_store_client.return_value = mock_vs

    with patch("repository.pipeline_ingest_documents.RagEmbeddings"), patch(
        "repository.pipeline_ingest_documents.VectorStoreRepository"
    ) as mock_vs_repo, patch("repository.pipeline_ingest_documents.RepositoryServiceFactory") as mock_factory:
        mock_vs_repo.return_value.find_repository_by_id.return_value = {"repositoryId": "repo1", "type": "opensearch"}
        mock_factory.create_service.return_value = mock_service

        from repository.pipeline_ingest_documents import remove_document_from_vectorstore

        remove_document_from_vectorstore(doc)

        mock_vs.delete.assert_called_once_with(["sub1", "sub2"])


def test_pipeline_ingest_documents_batch(setup_env):
    """Test pipeline_ingest_documents processes batch ingestion."""
    from models.domain_objects import FixedChunkingStrategy, IngestionJob, IngestionStatus, JobActionType

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="",
        embedding_model="model1",
        username="user1",
        job_type=JobActionType.DOCUMENT_BATCH_INGESTION,
        chunk_strategy=FixedChunkingStrategy(size=1000, overlap=100),
        s3_paths=["s3://bucket/key1", "s3://bucket/key2", "s3://bucket/key3"],
    )

    with patch("repository.pipeline_ingest_documents.ingestion_job_repository") as mock_job_repo, patch(
        "repository.pipeline_ingest_documents.pipeline_ingest_document"
    ) as mock_ingest_doc:

        from repository.pipeline_ingest_documents import pipeline_ingest_documents

        pipeline_ingest_documents(job)

        assert mock_ingest_doc.call_count == 3
        mock_job_repo.update_status.assert_called_with(job, IngestionStatus.INGESTION_COMPLETED)


def test_pipeline_ingest_documents_batch_with_failures(setup_env):
    """Test pipeline_ingest_documents handles partial failures."""
    from models.domain_objects import FixedChunkingStrategy, IngestionJob, IngestionStatus, JobActionType

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="",
        embedding_model="model1",
        username="user1",
        job_type=JobActionType.DOCUMENT_BATCH_INGESTION,
        chunk_strategy=FixedChunkingStrategy(size=1000, overlap=100),
        s3_paths=["s3://bucket/key1", "s3://bucket/key2", "s3://bucket/key3"],
    )

    with patch("repository.pipeline_ingest_documents.ingestion_job_repository") as mock_job_repo, patch(
        "repository.pipeline_ingest_documents.pipeline_ingest_document"
    ) as mock_ingest_doc:

        # First succeeds, second fails, third succeeds
        mock_ingest_doc.side_effect = [None, Exception("Ingest failed"), None]

        from repository.pipeline_ingest_documents import pipeline_ingest_documents

        pipeline_ingest_documents(job)

        assert mock_ingest_doc.call_count == 3
        mock_job_repo.update_status.assert_called_with(job, IngestionStatus.INGESTION_FAILED)


def test_pipeline_ingest_documents_batch_exceeds_limit(setup_env):
    """Test pipeline_ingest_documents rejects batch over 100 documents."""
    from models.domain_objects import FixedChunkingStrategy, IngestionJob, JobActionType

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="",
        embedding_model="model1",
        username="user1",
        job_type=JobActionType.DOCUMENT_BATCH_INGESTION,
        chunk_strategy=FixedChunkingStrategy(size=1000, overlap=100),
        s3_paths=[f"s3://bucket/key{i}" for i in range(101)],
    )

    with patch("repository.pipeline_ingest_documents.ingestion_job_repository") as mock_job_repo:
        from repository.pipeline_ingest_documents import pipeline_ingest_documents

        with pytest.raises(Exception):
            pipeline_ingest_documents(job)

        mock_job_repo.update_status.assert_called()


def test_pipeline_ingest_documents_batch_missing_metadata(setup_env):
    """Test pipeline_ingest_documents raises error when s3_paths missing."""
    from models.domain_objects import FixedChunkingStrategy, IngestionJob, JobActionType

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="",
        embedding_model="model1",
        username="user1",
        job_type=JobActionType.DOCUMENT_BATCH_INGESTION,
        chunk_strategy=FixedChunkingStrategy(size=1000, overlap=100),
        s3_paths=None,
    )

    with patch("repository.pipeline_ingest_documents.ingestion_job_repository") as mock_job_repo:
        from repository.pipeline_ingest_documents import pipeline_ingest_documents

        with pytest.raises(Exception):
            pipeline_ingest_documents(job)

        mock_job_repo.update_status.assert_called()


def test_pipeline_ingest_routes_to_batch_ingestion(setup_env):
    """Test pipeline_ingest routes to batch document ingestion."""
    from models.domain_objects import FixedChunkingStrategy, IngestionJob, JobActionType

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="",
        embedding_model="model1",
        username="user1",
        job_type=JobActionType.DOCUMENT_BATCH_INGESTION,
        chunk_strategy=FixedChunkingStrategy(size=1000, overlap=100),
        s3_paths=["s3://bucket/key1"],
    )

    with patch("repository.pipeline_ingest_documents.pipeline_ingest_documents") as mock_ingest_documents:
        from repository.pipeline_ingest_documents import pipeline_ingest

        pipeline_ingest(job)

        mock_ingest_documents.assert_called_once_with(job)


def test_pipeline_ingest_routes_to_single_ingestion(setup_env):
    """Test pipeline_ingest routes to single document ingestion."""
    from models.domain_objects import FixedChunkingStrategy, IngestionJob

    job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="s3://bucket/key",
        embedding_model="model1",
        username="user1",
        chunk_strategy=FixedChunkingStrategy(size=1000, overlap=100),
    )

    with patch("repository.pipeline_ingest_documents.pipeline_ingest_document") as mock_ingest_document:
        from repository.pipeline_ingest_documents import pipeline_ingest

        pipeline_ingest(job)

        mock_ingest_document.assert_called_once_with(job)
