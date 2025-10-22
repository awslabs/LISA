#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import sys
from unittest.mock import MagicMock, patch, Mock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Setup environment variables for all tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("LISA_RAG_VECTOR_STORE_TABLE", "test-table")
    # Clear any cached modules
    import sys
    if 'repository.vector_store_repo' in sys.modules:
        del sys.modules['repository.vector_store_repo']


def test_vector_store_repo_find_by_id():
    """Test vector store repository find by id"""
    with patch("boto3.resource") as mock_resource:
        mock_table = Mock()
        mock_resource.return_value.Table.return_value = mock_table
        
        from repository.vector_store_repo import VectorStoreRepository
        repo = VectorStoreRepository()
        
        mock_table.get_item.return_value = {
            "Item": {
                "repositoryId": "test-repo",
                "config": {
                    "repositoryId": "test-repo",
                    "name": "Test Repo",
                    "type": "opensearch",
                    "status": "active",
                },
                "status": "active",
            }
        }
        
        result = repo.find_repository_by_id("test-repo")
        
        assert result is not None
        assert result["repositoryId"] == "test-repo"
        mock_table.get_item.assert_called_once()


def test_vector_store_repo_get_registered():
    """Test vector store repository get registered repositories"""
    with patch("boto3.resource") as mock_resource:
        mock_table = Mock()
        mock_resource.return_value.Table.return_value = mock_table
        
        from repository.vector_store_repo import VectorStoreRepository
        repo = VectorStoreRepository()
        
        mock_table.scan.return_value = {
            "Items": [
                {
                    "repositoryId": "repo1",
                    "config": {
                        "repositoryId": "repo1",
                        "name": "Repo 1",
                        "type": "opensearch",
                        "status": "active",
                    },
                    "status": "active",
                }
            ]
        }
        
        result = repo.get_registered_repositories()
        
        assert len(result) == 1
        mock_table.scan.assert_called_once()


def test_vector_store_repo_save():
    """Test vector store repository save"""
    with patch("boto3.resource") as mock_resource:
        mock_table = Mock()
        mock_resource.return_value.Table.return_value = mock_table
        
        from repository.vector_store_repo import VectorStoreRepository
        repo = VectorStoreRepository()
        
        # Mock get_item for update method
        mock_table.get_item.return_value = {
            "Item": {
                "repositoryId": "test-repo",
                "config": {},
            }
        }
        mock_table.update_item.return_value = {}
        
        repo_data = {
            "repositoryId": "test-repo",
            "name": "Test Repo",
            "type": "opensearch",
            "status": "active",
        }
        
        repo.update("test-repo", repo_data)
        
        mock_table.update_item.assert_called_once()


def test_vector_store_repo_delete():
    """Test vector store repository delete"""
    with patch("boto3.resource") as mock_resource:
        mock_table = Mock()
        mock_resource.return_value.Table.return_value = mock_table
        
        from repository.vector_store_repo import VectorStoreRepository
        repo = VectorStoreRepository()
        
        mock_table.delete_item.return_value = {}
        
        repo.delete("test-repo")
        
        mock_table.delete_item.assert_called_once()


def test_vector_store_repo_get_status():
    """Test vector store repository get status"""
    with patch("boto3.resource") as mock_resource:
        mock_table = Mock()
        mock_resource.return_value.Table.return_value = mock_table
        
        from repository.vector_store_repo import VectorStoreRepository
        repo = VectorStoreRepository()
        
        mock_table.scan.return_value = {
            "Items": [
                {
                    "repositoryId": "repo1",
                    "status": "active",
                }
            ]
        }
        
        result = repo.get_repository_status()
        
        assert "repo1" in result
        assert result["repo1"] == "active"
        mock_table.scan.assert_called_once()
