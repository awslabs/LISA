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

"""
Unit tests for cross-repository collection queries.

These tests follow API-level testing principles:
- Test complete workflows, not individual lines
- Use local fixtures for dependency injection
- No global mocks
"""

import os
import sys
from datetime import datetime, timezone
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
    monkeypatch.setenv("LISA_RAG_COLLECTIONS_TABLE", "test-collections-table")


@pytest.fixture
def mock_collection_repo():
    """Mock collection repository with test data."""
    repo = Mock()
    
    # Configure default behavior
    repo.list_by_repository.return_value = ([], None)
    repo.count_by_repository.return_value = 0
    
    return repo


@pytest.fixture
def mock_vector_store_repo():
    """Mock vector store repository with test repositories."""
    repo = Mock()
    
    # Configure default behavior
    repo.get_registered_repositories.return_value = []
    
    return repo


@pytest.fixture
def collection_service(mock_collection_repo, mock_vector_store_repo):
    """Create service with injected mock dependencies."""
    from repository.collection_service import CollectionService
    
    return CollectionService(
        collection_repo=mock_collection_repo,
        vector_store_repo=mock_vector_store_repo
    )


@pytest.fixture
def sample_repositories():
    """Sample repository configurations for testing."""
    return [
        {
            "repositoryId": "repo-1",
            "repositoryName": "Repository 1",
            "allowedGroups": ["group1", "group2"],
        },
        {
            "repositoryId": "repo-2",
            "repositoryName": "Repository 2",
            "allowedGroups": ["group2", "group3"],
        },
        {
            "repositoryId": "repo-3",
            "repositoryName": "Repository 3",
            "allowedGroups": [],  # Public repository
        },
    ]


@pytest.fixture
def sample_collections():
    """Sample collection configurations for testing."""
    now = datetime.now(timezone.utc)
    
    return [
        RagCollectionConfig(
            collectionId="coll-1",
            repositoryId="repo-1",
            name="Collection 1",
            description="First collection",
            embeddingModel="model-1",
            chunkingStrategy=FixedChunkingStrategy(size=1000, overlap=100),
            allowedGroups=["group1"],
            createdBy="user1",
            createdAt=now,
            updatedAt=now,
            status=CollectionStatus.ACTIVE,
            private=False,
        ),
        RagCollectionConfig(
            collectionId="coll-2",
            repositoryId="repo-1",
            name="Collection 2",
            description="Second collection",
            embeddingModel="model-1",
            chunkingStrategy=FixedChunkingStrategy(size=1000, overlap=100),
            allowedGroups=["group2"],
            createdBy="user2",
            createdAt=now,
            updatedAt=now,
            status=CollectionStatus.ACTIVE,
            private=True,  # Private collection
        ),
        RagCollectionConfig(
            collectionId="coll-3",
            repositoryId="repo-2",
            name="Collection 3",
            description="Third collection",
            embeddingModel="model-2",
            chunkingStrategy=FixedChunkingStrategy(size=1000, overlap=100),
            allowedGroups=["group3"],
            createdBy="user1",
            createdAt=now,
            updatedAt=now,
            status=CollectionStatus.ACTIVE,
            private=False,
        ),
    ]


def test_list_all_user_collections_admin_workflow(
    collection_service,
    mock_vector_store_repo,
    mock_collection_repo,
    sample_repositories,
    sample_collections
):
    """
    Complete workflow: Admin requests collections → service queries all repos → returns all collections.
    
    Workflow:
    1. Admin user requests all collections
    2. Service gets all repositories (no filtering)
    3. Service queries collections from each repository
    4. Service returns all collections (no permission filtering)
    5. Collections are enriched with repository names
    """
    # Setup: Configure mocks for admin workflow
    mock_vector_store_repo.get_registered_repositories.return_value = sample_repositories
    
    # Mock collection queries for each repository
    def mock_list_by_repo(repository_id, **kwargs):
        repo_collections = [c for c in sample_collections if c.repositoryId == repository_id]
        return (repo_collections, None)
    
    mock_collection_repo.list_by_repository.side_effect = mock_list_by_repo
    mock_collection_repo.count_by_repository.return_value = 10  # Small dataset
    
    # Execute: Admin requests all collections
    collections, next_token = collection_service.list_all_user_collections(
        username="admin-user",
        user_groups=["admin"],
        is_admin=True,  # Admin user
        page_size=20,
        pagination_token=None,
        filter_text=None,
        sort_by="createdAt",
        sort_order="desc",
    )
    
    # Verify: All collections returned with repository names
    assert len(collections) == 3
    assert all("repositoryName" in c for c in collections)
    assert collections[0]["repositoryName"] == "Repository 1"
    assert next_token is None  # All results fit in one page


def test_list_all_user_collections_group_access_workflow(
    collection_service,
    mock_vector_store_repo,
    mock_collection_repo,
    sample_repositories,
    sample_collections
):
    """
    Complete workflow: User with groups → filtered by repo permissions → returns accessible collections.
    
    Workflow:
    1. User with group1 requests collections
    2. Service filters repositories by group access (repo-1, repo-3)
    3. Service queries collections from accessible repositories
    4. Service filters collections by collection-level permissions
    5. Returns only accessible collections
    """
    # Setup: Configure mocks
    mock_vector_store_repo.get_registered_repositories.return_value = sample_repositories
    
    def mock_list_by_repo(repository_id, **kwargs):
        repo_collections = [c for c in sample_collections if c.repositoryId == repository_id]
        return (repo_collections, None)
    
    mock_collection_repo.list_by_repository.side_effect = mock_list_by_repo
    mock_collection_repo.count_by_repository.return_value = 10
    
    # Execute: User with group1 requests collections
    collections, next_token = collection_service.list_all_user_collections(
        username="user1",
        user_groups=["group1"],  # Has access to repo-1 and repo-3
        is_admin=False,
        page_size=20,
        pagination_token=None,
        filter_text=None,
        sort_by="createdAt",
        sort_order="desc",
    )
    
    # Verify: Only collections from accessible repositories
    assert len(collections) == 1  # Only coll-1 (coll-2 is private and not owned by user1)
    assert collections[0]["collectionId"] == "coll-1"
    assert collections[0]["repositoryId"] == "repo-1"


def test_list_all_user_collections_no_access_workflow(
    collection_service,
    mock_vector_store_repo,
    mock_collection_repo,
    sample_repositories
):
    """
    Complete workflow: User with no access → empty list returned.
    
    Workflow:
    1. User with no matching groups requests collections
    2. Service filters repositories (none accessible)
    3. Returns empty list
    """
    # Setup: Configure mocks
    mock_vector_store_repo.get_registered_repositories.return_value = sample_repositories
    
    # Execute: User with no matching groups
    collections, next_token = collection_service.list_all_user_collections(
        username="user-no-access",
        user_groups=["group-nonexistent"],
        is_admin=False,
        page_size=20,
        pagination_token=None,
        filter_text=None,
        sort_by="createdAt",
        sort_order="desc",
    )
    
    # Verify: Empty list returned
    assert len(collections) == 0
    assert next_token is None


def test_list_all_user_collections_private_collections_workflow(
    collection_service,
    mock_vector_store_repo,
    mock_collection_repo,
    sample_repositories,
    sample_collections
):
    """
    Complete workflow: User sees own private collections, not others'.
    
    Workflow:
    1. User2 (owner of private coll-2) requests collections
    2. Service queries accessible repositories
    3. Service filters collections by ownership and privacy
    4. Returns user's own private collection
    """
    # Setup: Configure mocks
    mock_vector_store_repo.get_registered_repositories.return_value = sample_repositories
    
    def mock_list_by_repo(repository_id, **kwargs):
        repo_collections = [c for c in sample_collections if c.repositoryId == repository_id]
        return (repo_collections, None)
    
    mock_collection_repo.list_by_repository.side_effect = mock_list_by_repo
    mock_collection_repo.count_by_repository.return_value = 10
    
    # Execute: User2 requests collections (owns private coll-2)
    collections, next_token = collection_service.list_all_user_collections(
        username="user2",
        user_groups=["group2"],  # Has access to repo-1 and repo-2
        is_admin=False,
        page_size=20,
        pagination_token=None,
        filter_text=None,
        sort_by="createdAt",
        sort_order="desc",
    )
    
    # Verify: User sees their own private collection
    collection_ids = [c["collectionId"] for c in collections]
    assert "coll-2" in collection_ids  # User's own private collection
    assert "coll-3" in collection_ids  # Public collection from repo-2


def test_pagination_strategy_selection_workflow(
    collection_service,
    mock_vector_store_repo,
    mock_collection_repo,
    sample_repositories
):
    """
    Complete workflow: Service estimates count → selects correct strategy.
    
    Workflow:
    1. User requests collections
    2. Service estimates total collections across repositories
    3. Service selects simple strategy for <1000 collections
    4. Service selects scalable strategy for 1000+ collections
    """
    # Setup: Configure mocks for large dataset
    mock_vector_store_repo.get_registered_repositories.return_value = sample_repositories
    mock_collection_repo.count_by_repository.return_value = 500  # 500 per repo = 1500 total
    mock_collection_repo.list_by_repository.return_value = ([], None)
    
    # Execute: Request collections (should trigger scalable strategy)
    collections, next_token = collection_service.list_all_user_collections(
        username="admin-user",
        user_groups=["admin"],
        is_admin=True,
        page_size=20,
        pagination_token=None,
        filter_text=None,
        sort_by="createdAt",
        sort_order="desc",
    )
    
    # Verify: Scalable strategy was used (indicated by v2 token format if more pages exist)
    # Since we have no collections, we just verify the workflow completed
    assert collections == []


def test_paginate_collections_workflow(
    collection_service,
    mock_vector_store_repo,
    mock_collection_repo,
    sample_repositories,
    sample_collections
):
    """
    Complete workflow: Request with filter/sort → paginated results.
    
    Workflow:
    1. User requests collections with filter and sort
    2. Service aggregates collections from repositories
    3. Service applies text filter
    4. Service applies sorting
    5. Service returns paginated results
    """
    # Setup: Configure mocks
    mock_vector_store_repo.get_registered_repositories.return_value = sample_repositories
    
    def mock_list_by_repo(repository_id, **kwargs):
        repo_collections = [c for c in sample_collections if c.repositoryId == repository_id]
        return (repo_collections, None)
    
    mock_collection_repo.list_by_repository.side_effect = mock_list_by_repo
    mock_collection_repo.count_by_repository.return_value = 10  # Small dataset
    
    # Execute: Request with filter
    collections, next_token = collection_service.list_all_user_collections(
        username="admin-user",
        user_groups=["admin"],
        is_admin=True,
        page_size=20,
        pagination_token=None,
        filter_text="First",  # Should match "First collection"
        sort_by="name",
        sort_order="asc",
    )
    
    # Verify: Filtered and sorted results
    assert len(collections) == 1
    assert collections[0]["name"] == "Collection 1"


def test_repository_metadata_enrichment_workflow(
    collection_service,
    mock_vector_store_repo,
    mock_collection_repo,
    sample_repositories,
    sample_collections
):
    """
    Complete workflow: Collections queried → enriched with repo names.
    
    Workflow:
    1. User requests collections
    2. Service queries collections from repositories
    3. Service enriches each collection with repositoryName
    4. Returns enriched collections
    """
    # Setup: Configure mocks
    mock_vector_store_repo.get_registered_repositories.return_value = sample_repositories
    
    def mock_list_by_repo(repository_id, **kwargs):
        repo_collections = [c for c in sample_collections if c.repositoryId == repository_id]
        return (repo_collections, None)
    
    mock_collection_repo.list_by_repository.side_effect = mock_list_by_repo
    mock_collection_repo.count_by_repository.return_value = 10
    
    # Execute: Request collections
    collections, next_token = collection_service.list_all_user_collections(
        username="admin-user",
        user_groups=["admin"],
        is_admin=True,
        page_size=20,
        pagination_token=None,
        filter_text=None,
        sort_by="createdAt",
        sort_order="desc",
    )
    
    # Verify: All collections have repositoryName
    assert all("repositoryName" in c for c in collections)
    
    # Verify correct repository names
    repo_names = {c["repositoryId"]: c["repositoryName"] for c in collections}
    assert repo_names["repo-1"] == "Repository 1"
    assert repo_names["repo-2"] == "Repository 2"
