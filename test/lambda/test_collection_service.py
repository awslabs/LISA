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

from models.domain_objects import CollectionMetadata, CollectionStatus, FixedChunkingStrategy, RagCollectionConfig


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Setup environment variables for all tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")


def test_create_collection():
    """Test collection creation"""
    from repository.collection_service import CollectionService
    from utilities.repository_types import RepositoryType

    mock_repo = Mock()
    mock_vector_store_repo = Mock()
    mock_document_repo = Mock()
    service = CollectionService(mock_repo, mock_vector_store_repo, mock_document_repo)

    repository = {
        "repositoryId": "test-repo",
        "type": RepositoryType.OPENSEARCH,
    }

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
    result = service.create_collection(repository, collection, "user")

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

    mock_repo.list_by_repository.return_value = ([collection], None)
    result, key = service.list_collections("test-repo", "user", ["group1"], False)

    assert len(result) == 1
    assert result[0].collectionId == "test-coll"


def test_delete_collection():
    """Test delete collection"""
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

        service.delete_collection("test-repo", "test-coll", "user", ["group1"], False)

    # Verify status was updated to DELETE_IN_PROGRESS
    mock_repo.update.assert_called()
    # Verify ingestion job was saved and submitted
    mock_ingestion_job_repo.save.assert_called_once()
    mock_ingestion_service.create_delete_job.assert_called_once()


class TestCollectionMetadataMerging:
    """Test metadata merging from repository, collection, and passed-in metadata."""

    @pytest.fixture
    def service(self, setup_env):
        """Create CollectionService instance with mocked repositories."""
        from repository.collection_service import CollectionService

        # Create service without initializing repositories (they're not needed for metadata merging)
        service = CollectionService.__new__(CollectionService)
        service.collection_repo = None
        service.vector_store_repo = None
        return service

    def test_metadata_merging_all_layers(self, service):
        """Test metadata from all three layers are merged with correct precedence."""
        repository = {
            "metadata": CollectionMetadata(
                customFields={
                    "repo_key": "repo_value",
                    "shared_key": "from_repo",
                    "override_key": "from_repo",
                }
            )
        }
        collection = RagCollectionConfig(
            collectionId="test-collection",
            repositoryId="test-repo",
            name="Test Collection",
            embeddingModel="test-model",
            createdBy="test-user",
            metadata=CollectionMetadata(
                customFields={
                    "collection_key": "collection_value",
                    "shared_key": "from_collection",
                    "override_key": "from_collection",
                }
            ),
        )
        passed_metadata = CollectionMetadata(
            customFields={
                "passed_key": "passed_value",
                "override_key": "from_passed",
            }
        )

        result = service.get_collection_metadata(repository, collection, passed_metadata)

        assert result["repo_key"] == "repo_value"
        assert result["collection_key"] == "collection_value"
        assert result["passed_key"] == "passed_value"
        assert result["shared_key"] == "from_collection"
        assert result["override_key"] == "from_passed"

    def test_metadata_merging_no_passed_metadata(self, service):
        """Test metadata merging when no passed metadata provided."""
        repository = {
            "metadata": CollectionMetadata(customFields={"repo_key": "repo_value", "shared_key": "from_repo"})
        }
        collection = RagCollectionConfig(
            collectionId="test-collection",
            repositoryId="test-repo",
            name="Test Collection",
            embeddingModel="test-model",
            createdBy="test-user",
            metadata=CollectionMetadata(
                customFields={"collection_key": "collection_value", "shared_key": "from_collection"}
            ),
        )

        result = service.get_collection_metadata(repository, collection, None)

        assert result["repo_key"] == "repo_value"
        assert result["collection_key"] == "collection_value"
        assert result["shared_key"] == "from_collection"

    def test_metadata_merging_no_collection_metadata(self, service):
        """Test metadata merging when collection has no metadata."""
        repository = {
            "metadata": CollectionMetadata(customFields={"repo_key": "repo_value", "shared_key": "from_repo"})
        }
        collection = RagCollectionConfig(
            collectionId="test-collection",
            repositoryId="test-repo",
            name="Test Collection",
            embeddingModel="test-model",
            createdBy="test-user",
            metadata=None,
        )
        passed_metadata = CollectionMetadata(customFields={"passed_key": "passed_value", "shared_key": "from_passed"})

        result = service.get_collection_metadata(repository, collection, passed_metadata)

        assert result["repo_key"] == "repo_value"
        assert result["passed_key"] == "passed_value"
        assert result["shared_key"] == "from_passed"

    def test_metadata_merging_no_repository_metadata(self, service):
        """Test metadata merging when repository has no metadata."""
        repository = {"metadata": None}
        collection = RagCollectionConfig(
            collectionId="test-collection",
            repositoryId="test-repo",
            name="Test Collection",
            embeddingModel="test-model",
            createdBy="test-user",
            metadata=CollectionMetadata(customFields={"collection_key": "collection_value"}),
        )
        passed_metadata = CollectionMetadata(customFields={"passed_key": "passed_value"})

        result = service.get_collection_metadata(repository, collection, passed_metadata)

        assert result["collection_key"] == "collection_value"
        assert result["passed_key"] == "passed_value"

    def test_metadata_merging_empty_metadata(self, service):
        """Test metadata merging when all metadata is empty or None."""
        repository = {"metadata": None}
        collection = RagCollectionConfig(
            collectionId="test-collection",
            repositoryId="test-repo",
            name="Test Collection",
            embeddingModel="test-model",
            createdBy="test-user",
            metadata=None,
        )

        result = service.get_collection_metadata(repository, collection, None)

        assert result == {}
