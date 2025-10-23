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

#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import sys
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

from models.domain_objects import CollectionStatus, FixedSizeChunkingStrategy, RagCollectionConfig


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Setup environment variables for all tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")


def test_create_collection():
    """Test collection creation"""
    from repository.collection_service import CollectionService

    with patch("repository.collection_repo.CollectionRepository") as MockRepo:
        mock_repo = Mock()
        MockRepo.return_value = mock_repo
        service = CollectionService(mock_repo)

        collection = RagCollectionConfig(
            collectionId="test-coll",
            repositoryId="test-repo",
            name="Test",
            embeddingModel="model",
            chunkingStrategy=FixedSizeChunkingStrategy(chunkSize=1000, chunkOverlap=100),
            allowedGroups=["group1"],
            createdBy="user",
            status=CollectionStatus.ACTIVE,
            private=False,
        )

        mock_repo.create.return_value = collection
        result = service.create_collection(collection, "user", False)

        assert result.collectionId == "test-coll"
        mock_repo.create.assert_called_once()


def test_get_collection():
    """Test get collection"""
    from repository.collection_service import CollectionService

    with patch("repository.collection_repo.CollectionRepository") as MockRepo:
        mock_repo = Mock()
        MockRepo.return_value = mock_repo
        service = CollectionService(mock_repo)

        collection = RagCollectionConfig(
            collectionId="test-coll",
            repositoryId="test-repo",
            name="Test",
            embeddingModel="model",
            chunkingStrategy=FixedSizeChunkingStrategy(chunkSize=1000, chunkOverlap=100),
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

    with patch("repository.collection_repo.CollectionRepository") as MockRepo:
        mock_repo = Mock()
        MockRepo.return_value = mock_repo
        service = CollectionService(mock_repo)

        collection = RagCollectionConfig(
            collectionId="test-coll",
            repositoryId="test-repo",
            name="Test",
            embeddingModel="model",
            chunkingStrategy=FixedSizeChunkingStrategy(chunkSize=1000, chunkOverlap=100),
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
    from repository.collection_service import CollectionService

    with patch("repository.collection_repo.CollectionRepository") as MockRepo:
        mock_repo = Mock()
        MockRepo.return_value = mock_repo
        service = CollectionService(mock_repo)

        collection = RagCollectionConfig(
            collectionId="test-coll",
            repositoryId="test-repo",
            name="Test",
            embeddingModel="model",
            chunkingStrategy=FixedSizeChunkingStrategy(chunkSize=1000, chunkOverlap=100),
            allowedGroups=["group1"],
            createdBy="user",
            status=CollectionStatus.ACTIVE,
            private=False,
        )

        mock_repo.find_by_id.return_value = collection
        mock_repo.delete.return_value = None

        service.delete_collection("test-repo", "test-coll", "user", ["group1"], False)

        mock_repo.delete.assert_called_once()
