#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import sys
from unittest.mock import MagicMock, patch, Mock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

from models.domain_objects import CollectionStatus, FixedSizeChunkingStrategy, RagCollectionConfig


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Setup environment variables for all tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("LISA_RAG_COLLECTIONS_TABLE", "test-table")


def test_collection_repo_create():
    """Test collection repository create"""
    with patch("boto3.resource") as mock_resource:
        mock_table = Mock()
        mock_resource.return_value.Table.return_value = mock_table
        
        from repository.collection_repo import CollectionRepository
        repo = CollectionRepository()
        
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
        
        mock_table.put_item.return_value = {}
        result = repo.create(collection)
        
        assert result.collectionId == "test-coll"
        mock_table.put_item.assert_called_once()


def test_collection_repo_get():
    """Test collection repository get"""
    with patch("boto3.resource") as mock_resource:
        mock_table = Mock()
        mock_resource.return_value.Table.return_value = mock_table
        
        from repository.collection_repo import CollectionRepository
        repo = CollectionRepository()
        
        mock_table.get_item.return_value = {
            "Item": {
                "collectionId": "test-coll",
                "repositoryId": "test-repo",
                "name": "Test",
                "embeddingModel": "model",
                "status": "ACTIVE",
                "allowedGroups": [],
                "createdBy": "user",
                "private": False,
                "chunkingStrategy": {"type": "FIXED_SIZE", "chunkSize": 1000, "chunkOverlap": 100},
            }
        }
        
        result = repo.find_by_id("test-coll", "test-repo")
        
        assert result is not None
        mock_table.get_item.assert_called_once()


def test_collection_repo_list():
    """Test collection repository list"""
    with patch("boto3.resource") as mock_resource:
        mock_table = Mock()
        mock_resource.return_value.Table.return_value = mock_table
        
        from repository.collection_repo import CollectionRepository
        repo = CollectionRepository()
        
        mock_table.query.return_value = {
            "Items": [
                {
                    "collectionId": "test-coll",
                    "repositoryId": "test-repo",
                    "name": "Test",
                    "status": "ACTIVE",
                    "allowedGroups": [],
                    "createdBy": "user",
                    "private": False,
                    "embeddingModel": "model",
                    "chunkingStrategy": {"type": "FIXED_SIZE", "chunkSize": 1000, "chunkOverlap": 100},
                }
            ]
        }
        
        result, key = repo.list_by_repository("test-repo")
        
        assert len(result) == 1
        mock_table.query.assert_called_once()


def test_collection_repo_delete():
    """Test collection repository delete"""
    with patch("boto3.resource") as mock_resource:
        mock_table = Mock()
        mock_resource.return_value.Table.return_value = mock_table
        
        from repository.collection_repo import CollectionRepository
        repo = CollectionRepository()
        
        mock_table.delete_item.return_value = {}
        repo.delete("test-coll", "test-repo")
        
        mock_table.delete_item.assert_called_once()
