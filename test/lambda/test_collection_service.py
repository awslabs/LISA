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
from unittest.mock import Mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

from models.domain_objects import CollectionStatus, FixedChunkingStrategy, RagCollectionConfig


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Setup environment variables for all tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")


def test_create_collection():
    """Test collection creation"""
    from repository.collection_service import CollectionService

    mock_repo = Mock()
    mock_vector_store_repo = Mock()
    mock_document_repo = Mock()
    service = CollectionService(mock_repo, mock_vector_store_repo, mock_document_repo)

    collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="Test",
        embeddingModel="model",
        chunkingStrategy=FixedChunkingStrategy(size=1000, overlap=100),
        allowedGroups=["group1"],
        createdBy="user",
        status=CollectionStatus.ACTIVE,
        private=False,
    )

    mock_repo.find_by_name.return_value = None  # No existing collection
    mock_repo.create.return_value = collection
    result = service.create_collection(collection, "user")

    assert result.collectionId == "test-coll"
    mock_repo.create.assert_called_once()


def test_get_collection():
    """Test get collection"""
    from repository.collection_service import CollectionService

    mock_repo = Mock()
    mock_vector_store_repo = Mock()
    mock_document_repo = Mock()
    service = CollectionService(mock_repo, mock_vector_store_repo, mock_document_repo)

    collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="Test",
        embeddingModel="model",
        chunkingStrategy=FixedChunkingStrategy(size=1000, overlap=100),
        allowedGroups=["group1"],
        createdBy="user",
        status=CollectionStatus.ACTIVE,
        private=False,
    )

    mock_repo.find_by_id.return_value = collection
    result = service.get_collection("test-repo", "test-coll", "user", ["group1"], False)

    assert result.collectionId == "test-coll"


def test_list_collections():
    """Test list collections"""

    from repository.collection_service import CollectionService

    mock_repo = Mock()
    mock_vector_store_repo = Mock()
    mock_document_repo = Mock()
    service = CollectionService(mock_repo, mock_vector_store_repo, mock_document_repo)

    collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="Test",
        embeddingModel="model",
        chunkingStrategy=FixedChunkingStrategy(size=1000, overlap=100),
        allowedGroups=["group1"],
        createdBy="user",
        status=CollectionStatus.ACTIVE,
        private=False,
    )

    # Mock repository with proper structure for service factory
    mock_repository = {
        "repositoryId": "test-repo",
        "type": "opensearch",
        "status": "CREATE_COMPLETE",
        "embeddingModelId": "model",
    }
    mock_vector_store_repo.find_repository_by_id.return_value = mock_repository
    mock_repo.list_by_repository.return_value = ([collection], None)

    result, key = service.list_collections("test-repo", "user", ["group1"], False)

    # Should return 2 collections: the test collection + default collection
    assert len(result) == 2
    # Find the test collection (not the default one)
    test_coll = [c for c in result if c.collectionId == "test-coll"][0]
    assert test_coll.collectionId == "test-coll"


def test_delete_collection():
    """Test delete regular collection (full deletion)"""
    from unittest.mock import patch

    from repository.collection_service import CollectionService

    mock_repo = Mock()
    mock_vector_store_repo = Mock()
    mock_document_repo = Mock()
    service = CollectionService(mock_repo, mock_vector_store_repo, mock_document_repo)

    collection = RagCollectionConfig(
        collectionId="test-coll",
        repositoryId="test-repo",
        name="Test",
        embeddingModel="model",
        chunkingStrategy=FixedChunkingStrategy(size=1000, overlap=100),
        allowedGroups=["group1"],
        createdBy="user",
        status=CollectionStatus.ACTIVE,
        private=False,
    )

    mock_repo.find_by_id.return_value = collection
    mock_repo.update.return_value = None

    # Mock the dependencies created inside delete_collection
    mock_ingestion_job_repo = Mock()
    mock_ingestion_service = Mock()

    with patch("repository.collection_service.IngestionJobRepository", return_value=mock_ingestion_job_repo), patch(
        "repository.collection_service.DocumentIngestionService", return_value=mock_ingestion_service
    ):

        result = service.delete_collection(
            repository_id="test-repo",
            collection_id="test-coll",
            embedding_name=None,
            username="user",
            user_groups=["group1"],
            is_admin=False,
        )

    # Verify result contains deletion type
    assert result["deletionType"] == "full"
    assert "jobId" in result
    assert "status" in result

    # Verify status was updated to DELETE_IN_PROGRESS
    mock_repo.update.assert_called()
    # Verify ingestion job was saved and submitted
    mock_ingestion_job_repo.save.assert_called_once()
    mock_ingestion_service.create_delete_job.assert_called_once()


def test_delete_default_collection():
    """Test delete default collection (partial deletion)"""
    from unittest.mock import patch

    from repository.collection_service import CollectionService

    mock_repo = Mock()
    mock_vector_store_repo = Mock()
    mock_document_repo = Mock()
    service = CollectionService(mock_repo, mock_vector_store_repo, mock_document_repo)

    # Mock the dependencies created inside delete_collection
    mock_ingestion_job_repo = Mock()
    mock_ingestion_service = Mock()

    with patch("repository.collection_service.IngestionJobRepository", return_value=mock_ingestion_job_repo), patch(
        "repository.collection_service.DocumentIngestionService", return_value=mock_ingestion_service
    ):

        result = service.delete_collection(
            repository_id="test-repo",
            collection_id=None,
            embedding_name="test-embedding-model",
            username="user",
            user_groups=["group1"],
            is_admin=True,
        )

    # Verify result contains deletion type
    assert result["deletionType"] == "partial"
    assert "jobId" in result
    assert "status" in result

    # Verify status was NOT updated (no collection_id)
    mock_repo.update.assert_not_called()
    mock_repo.find_by_id.assert_not_called()

    # Verify ingestion job was saved and submitted
    mock_ingestion_job_repo.save.assert_called_once()
    mock_ingestion_service.create_delete_job.assert_called_once()

    # Verify the ingestion job has correct fields
    saved_job = mock_ingestion_job_repo.save.call_args[0][0]
    assert saved_job.collection_id is None
    assert saved_job.embedding_model == "test-embedding-model"
    assert saved_job.collection_deletion is True
