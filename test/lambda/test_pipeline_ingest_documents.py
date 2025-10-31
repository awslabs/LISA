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

import os
import sys
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from models.domain_objects import (
    ChunkingStrategyType,
    FixedChunkingStrategy,
    IngestionJob,
    IngestionStatus,
    IngestionType,
    RagDocument,
)

# Patch environment variables for boto3
os.environ["AWS_REGION"] = "us-east-1"
os.environ["LISA_INGESTION_JOB_TABLE_NAME"] = "test-table"
os.environ["RAG_DOCUMENT_TABLE"] = "test-doc-table"
os.environ["RAG_SUB_DOCUMENT_TABLE"] = "test-subdoc-table"


def make_job():
    return IngestionJob(
        id="job-1",
        repository_id="repo-1",
        collection_id="coll-1",
        document_id="doc-1",
        s3_path="s3://bucket/key.txt",
        chunk_strategy=FixedChunkingStrategy(type=ChunkingStrategyType.FIXED, size=1000, overlap=200),
        status=IngestionStatus.INGESTION_PENDING,
        ingestion_type=IngestionType.MANUAL,
        username="user1",
        created_date="2024-01-01T00:00:00Z",
    )


def make_doc():
    return RagDocument(
        repository_id="repo-1",
        collection_id="coll-1",
        document_name="key.txt",
        source="s3://bucket/key.txt",
        subdocs=["chunk1", "chunk2"],
        chunk_strategy=FixedChunkingStrategy(type=ChunkingStrategyType.FIXED, size=1000, overlap=200),
        username="user1",
        ingestion_type=IngestionType.MANUAL,
    )


def test_pipeline_ingest_success():
    import repository.pipeline_ingest_documents as pid

    job = make_job()
    make_doc()
    with patch("repository.pipeline_ingest_documents.generate_chunks", return_value=[MagicMock()]), patch(
        "repository.pipeline_ingest_documents.prepare_chunks", return_value=(["text"], [{}])
    ), patch(
        "repository.pipeline_ingest_documents.store_chunks_in_vectorstore", return_value=["chunk1", "chunk2"]
    ), patch.object(
        pid.rag_document_repository, "find_by_source", return_value=[]
    ), patch.object(
        pid.rag_document_repository, "save"
    ), patch.object(
        pid.ingestion_job_repository, "save"
    ):
        pid.pipeline_ingest(job)


def test_pipeline_ingest_exception():
    import repository.pipeline_ingest_documents as pid

    job = make_job()
    with patch("repository.pipeline_ingest_documents.generate_chunks", side_effect=Exception("fail")), patch.object(
        pid.ingestion_job_repository, "update_status"
    ) as mock_update:
        with pytest.raises(Exception, match="Failed to process document: fail"):
            pid.pipeline_ingest(job)
        mock_update.assert_called_with(job, IngestionStatus.INGESTION_FAILED)


def test_remove_document_from_vectorstore():
    import repository.pipeline_ingest_documents as pid

    doc = make_doc()
    with patch("repository.pipeline_ingest_documents.RagEmbeddings"), patch(
        "repository.pipeline_ingest_documents.get_vector_store_client"
    ) as mock_vs:
        mock_vs.return_value.delete = MagicMock()
        pid.remove_document_from_vectorstore(doc)
        mock_vs.return_value.delete.assert_called_once_with(doc.subdocs)


def test_handle_pipeline_ingest_event():
    import repository.pipeline_ingest_documents as pid

    event = {
        "detail": {
            "bucket": "bucket",
            "key": "key.txt",
            "repositoryId": "repo-1",
            "pipelineConfig": {"embeddingModel": "coll-1", "chunkSize": 1000, "chunkOverlap": 200},
        },
        "username": "user1",
    }
    with patch.object(pid, "get_username", return_value="user1"), patch.object(pid, "IngestionJob"), patch.object(
        pid.ingestion_job_repository, "save"
    ), patch.object(pid.ingestion_service, "submit_create_job") as mock_create:
        pid.handle_pipeline_ingest_event(event, MagicMock())
        mock_create.assert_called()


def test_handle_pipline_ingest_schedule_success():
    import repository.pipeline_ingest_documents as pid

    event = {
        "detail": {
            "bucket": "bucket",
            "prefix": "prefix/",
            "repositoryId": "repo-1",
            "pipelineConfig": {"embeddingModel": "coll-1", "chunkSize": 1000, "chunkOverlap": 200},
        },
        "username": "user1",
    }
    paginator = MagicMock()
    paginator.paginate.return_value = [
        {"Contents": [{"Key": "prefix/file1.txt", "LastModified": datetime.now(timezone.utc)}]}
    ]
    with patch.object(pid, "get_username", return_value="user1"), patch.object(
        pid.s3, "get_paginator", return_value=paginator
    ), patch.object(pid.ingestion_job_repository, "save"), patch.object(
        pid.ingestion_service, "submit_create_job"
    ) as mock_create:
        pid.handle_pipline_ingest_schedule(event, MagicMock())
        mock_create.assert_called()


def test_handle_pipline_ingest_schedule_error():
    import repository.pipeline_ingest_documents as pid

    event = {
        "detail": {
            "bucket": "bucket",
            "prefix": "prefix/",
            "repositoryId": "repo-1",
            "pipelineConfig": {"embeddingModel": "coll-1", "chunkSize": 1000, "chunkOverlap": 200},
        },
        "username": "user1",
    }
    with patch.object(pid, "get_username", return_value="user1"), patch.object(
        pid.s3, "get_paginator", side_effect=Exception("fail")
    ):
        with pytest.raises(Exception, match="fail"):
            pid.handle_pipline_ingest_schedule(event, MagicMock())


def test_store_chunks_in_vectorstore_success():
    import repository.pipeline_ingest_documents as pid

    with patch("repository.pipeline_ingest_documents.RagEmbeddings"), patch(
        "repository.pipeline_ingest_documents.get_vector_store_client"
    ) as mock_vs:
        mock_vs.return_value.add_texts.return_value = ["id1", "id2"]
        texts = ["a", "b"]
        metadatas = [{}, {}]
        ids = pid.store_chunks_in_vectorstore(texts, metadatas, "repo-1", "coll-1", "embedding-model")
        assert ids == ["id1", "id2"]


def test_store_chunks_in_vectorstore_empty_batch():
    import repository.pipeline_ingest_documents as pid

    with patch("repository.pipeline_ingest_documents.RagEmbeddings"), patch(
        "repository.pipeline_ingest_documents.get_vector_store_client"
    ) as mock_vs:
        mock_vs.return_value.add_texts.return_value = []
        texts = ["a"]
        metadatas = [{}]
        with pytest.raises(Exception, match="Failed to store documents in vector store for batch 1"):
            pid.store_chunks_in_vectorstore(texts, metadatas, "repo-1", "coll-1", "embedding-model")


def test_batch_texts():
    import repository.pipeline_ingest_documents as pid

    texts = ["a", "b", "c", "d"]
    metadatas = [{}, {}, {}, {}]
    batches = pid.batch_texts(texts, metadatas, batch_size=2)
    assert len(batches) == 2
    assert batches[0][0] == ["a", "b"]
    assert batches[1][0] == ["c", "d"]


def test_extract_chunk_strategy():
    import repository.pipeline_ingest_documents as pid

    config = {"chunkSize": 1000, "chunkOverlap": 200}
    strategy = pid.extract_chunk_strategy(config)
    assert strategy.size == 1000
    assert strategy.overlap == 200


def test_prepare_chunks():
    import repository.pipeline_ingest_documents as pid

    docs = [MagicMock(page_content="abc", metadata={"meta": 1}), MagicMock(page_content="def", metadata={"meta": 2})]
    texts, metadatas = pid.prepare_chunks(docs, "repo-1")
    assert texts == ["abc", "def"]
    assert metadatas == [{"meta": 1, "repository_id": "repo-1"}, {"meta": 2, "repository_id": "repo-1"}]
