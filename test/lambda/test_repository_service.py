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
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Setup environment variables for all tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("LISA_RAG_VECTOR_STORE_TABLE", "test-table")


def test_get_repository():
    """Test get repository"""
    with patch("repository.repository_service._vs_repo") as mock_repo:
        mock_repo.find_repository_by_id.return_value = {
            "repositoryId": "test-repo",
            "name": "Test Repo",
            "status": "active",
        }
        from repository.repository_service import get_repository

        result = get_repository("test-repo")

        assert result is not None
        assert result["repositoryId"] == "test-repo"
        mock_repo.find_repository_by_id.assert_called_once_with("test-repo")


def test_list_repositories():
    """Test list repositories"""
    with patch("repository.repository_service._vs_repo") as mock_repo:
        from repository.repository_service import list_repositories

        mock_repo.get_registered_repositories.return_value = [
            {"repositoryId": "repo1", "name": "Repo 1"},
            {"repositoryId": "repo2", "name": "Repo 2"},
        ]

        result = list_repositories()

        assert len(result) == 2
        mock_repo.get_registered_repositories.assert_called_once()


def test_get_repository_status():
    """Test get repository status"""
    with patch("repository.repository_service._vs_repo") as mock_repo:
        from repository.repository_service import get_repository_status

        mock_repo.get_repository_status.return_value = {
            "repo1": "active",
            "repo2": "inactive",
        }

        result = get_repository_status()

        assert "repo1" in result
        assert result["repo1"] == "active"
        mock_repo.get_repository_status.assert_called_once()


def test_save_repository():
    """Test save repository"""
    with patch("repository.repository_service._vs_repo") as mock_repo:
        from repository.repository_service import save_repository

        mock_repo.update.return_value = None

        repo_data = {
            "repositoryId": "test-repo",
            "name": "Test Repo",
            "status": "active",
        }

        save_repository(repo_data)

        mock_repo.update.assert_called_once_with("test-repo", repo_data)


def test_delete_repository():
    """Test delete repository"""
    with patch("repository.repository_service._vs_repo") as mock_repo:
        from repository.repository_service import delete_repository

        mock_repo.delete.return_value = None

        delete_repository("test-repo")

        mock_repo.delete.assert_called_once_with("test-repo")
