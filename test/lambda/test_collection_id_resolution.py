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

"""Tests for pipeline collectionId resolution in ingest and delete handlers.

Pipeline configs may store a collection name (e.g. "default") as the collectionId
rather than the auto-generated UUID used as the collections table primary key.
These tests verify that find_by_id_or_name correctly resolves a name to its
corresponding UUID at read time, ensuring both ingest and delete handlers
operate on the correct collection.
"""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def setup_env(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("RAG_DOCUMENT_TABLE", "test-doc-table")
    monkeypatch.setenv("RAG_SUB_DOCUMENT_TABLE", "test-subdoc-table")
    monkeypatch.setenv("LISA_INGESTION_JOB_TABLE_NAME", "test-job-table")
    monkeypatch.setenv("LISA_INGESTION_JOB_QUEUE_NAME", "test-queue")
    monkeypatch.setenv("LISA_INGESTION_JOB_DEFINITION_NAME", "test-job-def")
    monkeypatch.setenv("LISA_RAG_VECTOR_STORE_TABLE", "test-vs-table")
    monkeypatch.setenv("LISA_RAG_COLLECTIONS_TABLE", "test-collections-table")


@pytest.fixture
def mock_dynamodb_table():
    return MagicMock()


@pytest.fixture
def collection_repo(mock_dynamodb_table, setup_env):
    with patch("boto3.resource") as mock_resource:
        mock_resource.return_value.Table.return_value = mock_dynamodb_table
        from repository.collection_repo import CollectionRepository

        return CollectionRepository()


def _make_collection_item(collection_id="uuid-123", name="default"):
    return {
        "collectionId": collection_id,
        "repositoryId": "repo1",
        "name": name,
        "status": "ACTIVE",
        "createdBy": "user1",
        "embeddingModel": "model1",
    }


# ---------------------------------------------------------------------------
# collection_repo.find_by_id_or_name
# ---------------------------------------------------------------------------


def test_find_by_id_or_name_hits_uuid_fast_path(collection_repo, mock_dynamodb_table):
    """Returns the collection directly when the provided value matches a UUID."""
    mock_dynamodb_table.get_item.return_value = {"Item": _make_collection_item()}

    result = collection_repo.find_by_id_or_name("uuid-123", "repo1")

    assert result is not None
    assert result.collectionId == "uuid-123"
    mock_dynamodb_table.get_item.assert_called_once()
    mock_dynamodb_table.query.assert_not_called()


def test_find_by_id_or_name_falls_back_to_name(collection_repo, mock_dynamodb_table):
    """Falls back to a name-based lookup when no UUID match is found."""
    mock_dynamodb_table.get_item.return_value = {}  # UUID not found
    mock_dynamodb_table.query.return_value = {"Items": [_make_collection_item()]}

    result = collection_repo.find_by_id_or_name("default", "repo1")

    assert result is not None
    assert result.collectionId == "uuid-123"
    assert result.name == "default"
    mock_dynamodb_table.query.assert_called_once()


def test_find_by_id_or_name_returns_none_when_both_miss(collection_repo, mock_dynamodb_table):
    """Returns None when neither UUID nor name lookup finds a matching collection."""
    mock_dynamodb_table.get_item.return_value = {}
    mock_dynamodb_table.query.return_value = {"Items": []}

    result = collection_repo.find_by_id_or_name("nonexistent", "repo1")

    assert result is None


def _build_real_collection_service(mock_dynamodb_table):
    """Wire real CollectionRepository (mocked DynamoDB) into real CollectionService."""
    from repository.collection_repo import CollectionRepository
    from repository.collection_service import CollectionService

    repo = CollectionRepository.__new__(CollectionRepository)
    repo.table = mock_dynamodb_table
    return CollectionService(collection_repo=repo)


def test_ingest_name_resolves_to_uuid_via_real_service(setup_env, mock_dynamodb_table):
    """Ingest handler resolves a collection name to its UUID before saving the job.

    When a pipeline config references a collection by name, the ingest handler
    must resolve that name to the collection's UUID so the job is persisted
    with the correct identifier.
    """
    # DynamoDB: get_item (UUID lookup) misses; query (name lookup) returns the collection
    mock_dynamodb_table.get_item.return_value = {}
    mock_dynamodb_table.query.return_value = {"Items": [_make_collection_item("uuid-abc", "default")]}

    real_svc = _build_real_collection_service(mock_dynamodb_table)

    event = {
        "detail": {
            "bucket": "b",
            "key": "doc.txt",
            "repositoryId": "repo1",
            "pipelineConfig": {
                "collectionId": "default",
                "chunkingStrategy": {"type": "fixed", "size": 512, "overlap": 51},
            },
        }
    }

    with patch("repository.pipeline_ingest_handlers.vs_repo") as mock_vs_repo, patch(
        "repository.pipeline_ingest_handlers.collection_service", real_svc
    ), patch("repository.pipeline_ingest_handlers.ingestion_job_repository") as mock_job_repo, patch(
        "repository.pipeline_ingest_handlers.ingestion_service"
    ):

        mock_vs_repo.find_repository_by_id.return_value = {"repositoryId": "repo1", "type": "opensearch"}

        from repository.pipeline_ingest_handlers import handle_pipeline_ingest_event

        handle_pipeline_ingest_event(event, None)

        saved_job = mock_job_repo.save.call_args[0][0]
        assert saved_job.collection_id == "uuid-abc", (
            f"Expected UUID 'uuid-abc', got '{saved_job.collection_id}'. "
            "Collection name was not resolved to UUID by CollectionService."
        )


def test_delete_name_resolves_to_uuid_via_real_service(setup_env, mock_dynamodb_table):
    """Delete handler resolves a collection name to its UUID before removing documents.

    When a pipeline config references a collection by name, the delete handler
    must resolve that name to the collection's UUID and proceed with document
    deletion rather than skipping the operation.
    """
    mock_dynamodb_table.get_item.return_value = {}
    mock_dynamodb_table.query.return_value = {"Items": [_make_collection_item("uuid-abc", "default")]}

    real_svc = _build_real_collection_service(mock_dynamodb_table)

    event = {
        "detail": {
            "bucket": "b",
            "key": "doc.txt",
            "repositoryId": "repo1",
            "pipelineConfig": {"collectionId": "default"},
        }
    }

    with patch("repository.pipeline_ingest_handlers.vs_repo") as mock_vs_repo, patch(
        "repository.pipeline_ingest_handlers.collection_service", real_svc
    ), patch("repository.pipeline_ingest_handlers.rag_document_repository") as mock_doc_repo, patch(
        "repository.pipeline_ingest_handlers.ingestion_job_repository"
    ), patch(
        "repository.pipeline_ingest_handlers.ingestion_service"
    ):

        mock_vs_repo.find_repository_by_id.return_value = {"repositoryId": "repo1", "type": "opensearch"}
        mock_doc_repo.find_by_source.return_value = []

        from repository.pipeline_ingest_handlers import handle_pipeline_delete_event

        handle_pipeline_delete_event(event, None)

        # find_by_source must be called — proves handler did not silently skip
        mock_doc_repo.find_by_source.assert_called_once()
        call_kwargs = mock_doc_repo.find_by_source.call_args
        actual_collection_id = call_kwargs[1].get("collection_id") or call_kwargs[0][1]
        assert actual_collection_id == "uuid-abc", (
            f"Expected UUID 'uuid-abc', got '{actual_collection_id}'. "
            "Collection name was not resolved to UUID, or the delete handler skipped the operation."
        )
