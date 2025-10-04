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
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from models.domain_objects import FixedChunkingStrategy, IngestionJob, IngestionStatus, IngestionType, RagDocument

# Patch environment variables for boto3
os.environ["AWS_REGION"] = "us-east-1"
os.environ["RAG_DOCUMENT_TABLE"] = "test-doc-table"
os.environ["RAG_SUB_DOCUMENT_TABLE"] = "test-subdoc-table"
os.environ["LISA_INGESTION_JOB_TABLE_NAME"] = "test-ingestion-job-table"
os.environ["MANAGEMENT_KEY_SECRET_NAME_PS"] = "test-management-key"
os.environ["LISA_RAG_VECTOR_STORE_TABLE"] = "test-rag-vs-table"

import repository.pipeline_delete_documents as pdd


def make_job():
    return IngestionJob(
        id="job-1",
        repository_id="repo-1",
        collection_id="coll-1",
        document_id="doc-1",
        s3_path="s3://bucket/key.txt",
        chunk_strategy=FixedChunkingStrategy(type="fixed", size=1000, overlap=200),
        status=IngestionStatus.DELETE_PENDING,
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
        chunk_strategy=FixedChunkingStrategy(type="fixed", size=1000, overlap=200),
        username="user1",
        ingestion_type=IngestionType.MANUAL,
    )


def test_pipeline_delete_success():
    """Test successful pipeline delete operation"""
    job = make_job()
    doc = make_doc()

    with patch.object(pdd.rag_document_repository, "find_by_id", return_value=doc), patch.object(
        pdd.vs_repo, "find_repository_by_id", return_value={"repositoryId": "repo-1", "type": "opensearch"}
    ), patch("repository.pipeline_delete_documents.remove_document_from_vectorstore") as mock_remove, patch.object(
        pdd.rag_document_repository, "delete_by_id"
    ) as mock_delete, patch.object(
        pdd.ingestion_job_repository, "update_status"
    ) as mock_update:

        pdd.pipeline_delete(job)

        mock_remove.assert_called_once_with(doc)
        mock_delete.assert_called_once_with(doc.document_id)
        mock_update.assert_called_with(job, IngestionStatus.DELETE_COMPLETED)


def test_pipeline_delete_no_document_found():
    """Test pipeline delete when no document is found"""

    job = make_job()

    with patch.object(pdd.rag_document_repository, "find_by_id", return_value=None), patch.object(
        pdd.ingestion_job_repository, "update_status"
    ) as mock_update:

        pdd.pipeline_delete(job)

        # Should still update status to completed even if no document found
        mock_update.assert_called_with(job, IngestionStatus.DELETE_COMPLETED)


def test_pipeline_delete_exception():
    """Test pipeline delete when an exception occurs"""

    job = make_job()

    with patch.object(pdd.rag_document_repository, "find_by_id", side_effect=Exception("Database error")), patch.object(
        pdd.ingestion_job_repository, "update_status"
    ) as mock_update:

        with pytest.raises(Exception, match="Failed to delete document: Database error"):
            pdd.pipeline_delete(job)

        mock_update.assert_called_with(job, IngestionStatus.DELETE_FAILED)


def test_pipeline_delete_vectorstore_exception():
    """Test pipeline delete when vectorstore removal fails"""

    job = make_job()
    doc = make_doc()

    with patch.object(pdd.rag_document_repository, "find_by_id", return_value=doc), patch.object(
        pdd.vs_repo, "find_repository_by_id", return_value={"repositoryId": "repo-1", "type": "opensearch"}
    ), patch(
        "repository.pipeline_delete_documents.remove_document_from_vectorstore",
        side_effect=Exception("Vector store error"),
    ), patch.object(
        pdd.ingestion_job_repository, "update_status"
    ) as mock_update:

        with pytest.raises(Exception, match="Failed to delete document: Vector store error"):
            pdd.pipeline_delete(job)

        mock_update.assert_called_with(job, IngestionStatus.DELETE_FAILED)


def test_handle_pipeline_delete_event_success():
    """Test successful pipeline delete event handling"""

    event = {
        "detail": {
            "bucket": "bucket",
            "key": "key.txt",
            "repositoryId": "repo-1",
            "pipelineConfig": {"embeddingModel": "coll-1"},
        }
    }
    doc = make_doc()

    with patch.object(pdd.rag_document_repository, "find_by_source", return_value=[doc]), patch.object(
        pdd.ingestion_job_repository, "find_by_document", return_value=None
    ), patch.object(pdd.ingestion_service, "create_delete_job") as mock_create:

        pdd.handle_pipeline_delete_event(event, MagicMock())

        mock_create.assert_called_once()
        job = mock_create.call_args[0][0]
        assert job.repository_id == "repo-1"
        assert job.s3_path == "s3://bucket/key.txt"


def test_handle_pipeline_delete_event_with_existing_job():
    """Test pipeline delete event handling when ingestion job already exists"""

    event = {
        "detail": {
            "bucket": "bucket",
            "key": "key.txt",
            "repositoryId": "repo-1",
            "pipelineConfig": {"embeddingModel": "coll-1"},
        }
    }
    doc = make_doc()
    existing_job = make_job()

    with patch.object(pdd.rag_document_repository, "find_by_source", return_value=[doc]), patch.object(
        pdd.ingestion_job_repository, "find_by_document", return_value=existing_job
    ), patch.object(pdd.ingestion_service, "create_delete_job") as mock_create:

        pdd.handle_pipeline_delete_event(event, MagicMock())

        mock_create.assert_called_once_with(existing_job)


def test_handle_pipeline_delete_event_no_documents():
    """Test pipeline delete event handling when no documents are found"""

    event = {
        "detail": {
            "bucket": "bucket",
            "key": "key.txt",
            "repositoryId": "repo-1",
            "pipelineConfig": {"embeddingModel": "coll-1"},
        }
    }

    with patch.object(pdd.rag_document_repository, "find_by_source", return_value=[]), patch.object(
        pdd.ingestion_service, "create_delete_job"
    ) as mock_create:

        pdd.handle_pipeline_delete_event(event, MagicMock())

        # Should not create any jobs if no documents found
        mock_create.assert_not_called()


def test_handle_pipeline_delete_event_multiple_documents():
    """Test pipeline delete event handling with multiple documents"""

    event = {
        "detail": {
            "bucket": "bucket",
            "key": "key.txt",
            "repositoryId": "repo-1",
            "pipelineConfig": {"embeddingModel": "coll-1"},
        }
    }
    doc1 = make_doc()
    doc2 = make_doc()
    doc2.document_id = "doc-2"

    with patch.object(pdd.rag_document_repository, "find_by_source", return_value=[doc1, doc2]), patch.object(
        pdd.ingestion_job_repository, "find_by_document", return_value=None
    ), patch.object(pdd.ingestion_service, "create_delete_job") as mock_create:

        pdd.handle_pipeline_delete_event(event, MagicMock())

        # Should create jobs for both documents
        assert mock_create.call_count == 2


def test_handle_pipeline_delete_event_missing_detail():
    """Test pipeline delete event handling with missing detail"""

    event = {}

    with patch.object(pdd.rag_document_repository, "find_by_source", return_value=[]), patch.object(
        pdd.ingestion_service, "create_delete_job"
    ) as mock_create:

        pdd.handle_pipeline_delete_event(event, MagicMock())

        # Should handle gracefully with empty detail
        mock_create.assert_not_called()


def test_handle_pipeline_delete_event_missing_pipeline_config():
    """Test pipeline delete event handling with missing pipeline config"""

    event = {"detail": {"bucket": "bucket", "key": "key.txt", "repositoryId": "repo-1"}}

    with patch.object(pdd.rag_document_repository, "find_by_source", return_value=[]), patch.object(
        pdd.ingestion_service, "create_delete_job"
    ) as mock_create:

        pdd.handle_pipeline_delete_event(event, MagicMock())

        # Should handle gracefully with missing pipeline config
        mock_create.assert_not_called()


def test_handle_pipeline_delete_event_missing_embedding_model():
    """Test pipeline delete event handling with missing embedding model"""

    event = {"detail": {"bucket": "bucket", "key": "key.txt", "repositoryId": "repo-1", "pipelineConfig": {}}}

    with patch.object(pdd.rag_document_repository, "find_by_source", return_value=[]), patch.object(
        pdd.ingestion_service, "create_delete_job"
    ) as mock_create:

        pdd.handle_pipeline_delete_event(event, MagicMock())

        # Should handle gracefully with missing embedding model
        mock_create.assert_not_called()


def test_handle_pipeline_delete_event_repository_error():
    """Test pipeline delete event handling when repository lookup fails"""

    event = {
        "detail": {
            "bucket": "bucket",
            "key": "key.txt",
            "repositoryId": "repo-1",
            "pipelineConfig": {"embeddingModel": "coll-1"},
        }
    }

    with patch.object(
        pdd.rag_document_repository, "find_by_source", side_effect=Exception("Repository error")
    ), patch.object(pdd.ingestion_service, "create_delete_job") as mock_create:

        with pytest.raises(Exception, match="Repository error"):
            pdd.handle_pipeline_delete_event(event, MagicMock())

        mock_create.assert_not_called()


def test_handle_pipeline_delete_event_ingestion_service_error():
    """Test pipeline delete event handling when ingestion service fails"""

    event = {
        "detail": {
            "bucket": "bucket",
            "key": "key.txt",
            "repositoryId": "repo-1",
            "pipelineConfig": {"embeddingModel": "coll-1"},
        }
    }
    doc = make_doc()

    with patch.object(pdd.rag_document_repository, "find_by_source", return_value=[doc]), patch.object(
        pdd.ingestion_job_repository, "find_by_document", return_value=None
    ), patch.object(pdd.ingestion_service, "create_delete_job", side_effect=Exception("Service error")):

        with pytest.raises(Exception, match="Service error"):
            pdd.handle_pipeline_delete_event(event, MagicMock())
