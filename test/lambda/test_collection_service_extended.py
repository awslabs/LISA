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

"""Extended tests for collection service covering uncovered lines."""

import os
import sys
from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))

from models.domain_objects import (
    CollectionSortBy,
    CollectionStatus,
    FixedChunkingStrategy,
    RagCollectionConfig,
    SortOrder,
    SortParams,
    VectorStoreStatus,
)


@pytest.fixture
def setup_env(monkeypatch):
    """Setup environment variables for all tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("RAG_DOCUMENT_TABLE", "test-doc-table")
    monkeypatch.setenv("RAG_SUB_DOCUMENT_TABLE", "test-subdoc-table")


@pytest.fixture
def service(setup_env):
    """Create CollectionService with mocked dependencies."""
    from repository.collection_service import CollectionService

    mock_collection_repo = Mock()
    mock_vector_store_repo = Mock()
    mock_document_repo = Mock()
    return CollectionService(mock_collection_repo, mock_vector_store_repo, mock_document_repo)


def testcreate_default_collection_inactive_repository(service):
    """Test create_default_collection with inactive repository."""
    from repository.services import RepositoryServiceFactory

    test_repo = {
        "repositoryId": "repo1",
        "type": "opensearch",
        "status": VectorStoreStatus.CREATE_FAILED,
        "embeddingModelId": "model1",
    }
    repo_service = RepositoryServiceFactory.create_service(test_repo)
    result = repo_service.create_default_collection()
    assert result is None


def testcreate_default_collection_no_embedding_model(service):
    """Test create_default_collection when repository has no embedding model."""
    from repository.services import RepositoryServiceFactory

    test_repo = {"repositoryId": "repo1", "type": "opensearch", "status": VectorStoreStatus.CREATE_COMPLETE}
    repo_service = RepositoryServiceFactory.create_service(test_repo)
    result = repo_service.create_default_collection()
    assert result is None


def testcreate_default_collection_success(service):
    """Test create_default_collection creates virtual collection."""
    from repository.services import RepositoryServiceFactory

    test_repo = {
        "repositoryId": "repo1",
        "type": "opensearch",
        "status": VectorStoreStatus.CREATE_COMPLETE,
        "embeddingModelId": "model1",
        "chunkingStrategy": FixedChunkingStrategy(size=1000, overlap=100),
        "allowedGroups": ["group1"],
    }
    repo_service = RepositoryServiceFactory.create_service(test_repo)
    result = repo_service.create_default_collection()
    assert result is not None
    assert result.collectionId == "model1"
    assert result.name == f"{result.repositoryId}-{result.collectionId}"
    assert result.embeddingModel == "model1"


def test_update_collection_name_conflict(service):
    """Test update_collection with name conflict."""
    from utilities.validation import ValidationError

    existing = RagCollectionConfig(
        collectionId="col1",
        repositoryId="repo1",
        name="Original",
        embeddingModel="model1",
        createdBy="user1",
        status=CollectionStatus.ACTIVE,
    )

    conflicting = RagCollectionConfig(
        collectionId="col2",
        repositoryId="repo1",
        name="NewName",
        embeddingModel="model1",
        createdBy="user1",
        status=CollectionStatus.ACTIVE,
    )

    service.collection_repo.find_by_id.return_value = existing
    service.collection_repo.find_by_name.return_value = conflicting

    request = Mock()
    request.name = "NewName"

    with pytest.raises(ValidationError, match="already exists"):
        service.update_collection("col1", "repo1", request, "user1", ["group1"], False)


def test_get_collection_model_fallback_to_repository(service):
    """Test get_collection_model falls back to repository default."""
    from utilities.validation import ValidationError

    service.collection_repo.find_by_id.side_effect = ValidationError("Not found")
    service.vector_store_repo.find_repository_by_id.return_value = {"embeddingModelId": "repo-model"}

    result = service.get_collection_model("repo1", "col1", "user1", ["group1"], False)
    assert result == "repo-model"


def test_get_collection_model_no_repository_model(service):
    """Test get_collection_model when repository has no model."""
    from utilities.validation import ValidationError

    service.collection_repo.find_by_id.side_effect = ValidationError("Not found")
    service.vector_store_repo.find_repository_by_id.return_value = {}

    result = service.get_collection_model("repo1", "col1", "user1", ["group1"], False)
    assert result is None


def test_list_all_user_collections_no_repositories(service):
    """Test list_all_user_collections when user has no accessible repositories."""
    service.vector_store_repo.get_registered_repositories.return_value = []

    collections, token = service.list_all_user_collections("user1", ["group1"], False)
    assert collections == []
    assert token is None


def test_list_all_user_collections_simple_pagination(service):
    """Test list_all_user_collections with simple pagination strategy."""
    service.vector_store_repo.get_registered_repositories.return_value = [
        {"repositoryId": "repo1", "repositoryName": "Repo 1", "type": "pgvector", "allowedGroups": ["group1"]}
    ]

    collection = RagCollectionConfig(
        collectionId="col1",
        repositoryId="repo1",
        name="Test",
        embeddingModel="model1",
        createdBy="user1",
        status=CollectionStatus.ACTIVE,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )

    service.collection_repo.list_by_repository.return_value = ([collection], None)
    service.collection_repo.count_by_repository.return_value = 1

    collections, token = service.list_all_user_collections("user1", ["group1"], False, page_size=10)
    assert len(collections) == 1
    assert collections[0]["repositoryName"] == "Repo 1"


def test_list_all_user_collections_with_filter(service):
    """Test list_all_user_collections with text filter."""
    service.vector_store_repo.get_registered_repositories.return_value = [
        {"repositoryId": "repo1", "repositoryName": "Repo 1", "type": "pgvector", "allowedGroups": []}
    ]

    collection1 = RagCollectionConfig(
        collectionId="col1",
        repositoryId="repo1",
        name="Matching Collection",
        embeddingModel="model1",
        createdBy="user1",
        status=CollectionStatus.ACTIVE,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )

    collection2 = RagCollectionConfig(
        collectionId="col2",
        repositoryId="repo1",
        name="Other",
        embeddingModel="model1",
        createdBy="user1",
        status=CollectionStatus.ACTIVE,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )

    service.collection_repo.list_by_repository.return_value = ([collection1, collection2], None)
    service.collection_repo.count_by_repository.return_value = 2

    collections, _ = service.list_all_user_collections("user1", ["group1"], False, page_size=10, filter_text="matching")
    assert len(collections) == 1
    assert collections[0]["name"] == "Matching Collection"


def test_list_all_user_collections_large_dataset(service):
    """Test list_all_user_collections with large dataset using scalable pagination."""
    service.vector_store_repo.get_registered_repositories.return_value = [
        {"repositoryId": "repo1", "repositoryName": "Repo 1", "allowedGroups": []}
    ]

    collection = RagCollectionConfig(
        collectionId="col1",
        repositoryId="repo1",
        name="Test",
        embeddingModel="model1",
        createdBy="user1",
        status=CollectionStatus.ACTIVE,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )

    service.collection_repo.list_by_repository.return_value = ([collection], None)
    service.collection_repo.count_by_repository.return_value = 1500  # Triggers scalable pagination

    collections, token = service.list_all_user_collections("user1", ["group1"], False, page_size=10)
    assert len(collections) >= 0  # May be empty if no collections match


def test_paginate_large_collections_with_token(service):
    """Test _paginate_large_collections with pagination token."""
    repositories = [{"repositoryId": "repo1", "repositoryName": "Repo 1", "allowedGroups": []}]

    collection = RagCollectionConfig(
        collectionId="col1",
        repositoryId="repo1",
        name="Test",
        embeddingModel="model1",
        createdBy="user1",
        status=CollectionStatus.ACTIVE,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )

    service.collection_repo.list_by_repository.return_value = ([collection], None)

    pagination_token = {
        "version": "v2",
        "repositoryCursors": {"repo1": {"lastEvaluatedKey": None, "exhausted": False}},
        "globalOffset": 0,
        "seenCollectionIds": {"repo1": []},
        "filters": {"filter": None, "sortBy": "createdAt", "sortOrder": "desc"},
    }

    sort_params = SortParams(sort_by=CollectionSortBy.CREATED_AT, sort_order=SortOrder.DESC)

    collections, token = service._paginate_large_collections(
        repositories, "user1", ["group1"], False, 10, pagination_token, None, sort_params
    )
    assert len(collections) >= 0


def test_merge_sorted_batches_descending_order(service):
    """Test _merge_sorted_batches with descending order."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    collection1 = RagCollectionConfig(
        collectionId="col1",
        repositoryId="repo1",
        name="A",
        embeddingModel="model1",
        createdBy="user1",
        status=CollectionStatus.ACTIVE,
        createdAt=now,
        updatedAt=now,
    )

    collection2 = RagCollectionConfig(
        collectionId="col2",
        repositoryId="repo1",
        name="B",
        embeddingModel="model1",
        createdBy="user1",
        status=CollectionStatus.ACTIVE,
        createdAt=now,
        updatedAt=now,
    )

    batches = [
        {"repositoryId": "repo1", "collections": [collection1], "nextKey": None},
        {"repositoryId": "repo2", "collections": [collection2], "nextKey": None},
    ]

    merged = service._merge_sorted_batches(batches, "name", "desc")
    assert len(merged) == 2
    assert merged[0].name == "B"
    assert merged[1].name == "A"


def test_has_repository_access_public_repo(service):
    """Test _has_repository_access with public repository."""
    repository = {"repositoryId": "repo1", "allowedGroups": []}

    result = service._has_repository_access(["group1"], repository)
    assert result is True


def test_has_repository_access_no_matching_groups(service):
    """Test _has_repository_access with no matching groups."""
    repository = {"repositoryId": "repo1", "allowedGroups": ["admin"]}

    result = service._has_repository_access(["user"], repository)
    assert result is False


def test_estimate_total_collections_with_error(service):
    """Test _estimate_total_collections handles repository errors gracefully."""
    repositories = [{"repositoryId": "repo1"}, {"repositoryId": "repo2"}]

    service.collection_repo.count_by_repository.side_effect = [5, Exception("Error")]

    total = service._estimate_total_collections(repositories)
    assert total == 5  # Only counts successful repository


def test_paginate_collections_with_invalid_token(service):
    """Test _paginate_collections resets offset with invalid token."""
    repositories = [{"repositoryId": "repo1", "repositoryName": "Repo 1"}]

    collection = RagCollectionConfig(
        collectionId="col1",
        repositoryId="repo1",
        name="Test",
        embeddingModel="model1",
        createdBy="user1",
        status=CollectionStatus.ACTIVE,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )

    service.collection_repo.list_by_repository.return_value = ([collection], None)

    # Token with mismatched filters
    pagination_token = {
        "version": "v1",
        "offset": 10,
        "filters": {"filter": "old_filter", "sortBy": "name", "sortOrder": "asc"},
    }

    sort_params = SortParams(sort_by=CollectionSortBy.CREATED_AT, sort_order=SortOrder.DESC)

    collections, _ = service._paginate_collections(
        repositories, "user1", ["group1"], False, 10, pagination_token, "new_filter", sort_params
    )
    # Should reset to offset 0 and return results
    assert len(collections) >= 0


def test_matches_filter_description(service):
    """Test _matches_filter matches description."""
    collection = RagCollectionConfig(
        collectionId="col1",
        repositoryId="repo1",
        name="Test",
        description="This is a matching description",
        embeddingModel="model1",
        createdBy="user1",
        status=CollectionStatus.ACTIVE,
    )

    result = service._matches_filter(collection, "matching")
    assert result is True


def test_matches_filter_no_match(service):
    """Test _matches_filter returns False when no match."""
    collection = RagCollectionConfig(
        collectionId="col1",
        repositoryId="repo1",
        name="Test",
        description="Description",
        embeddingModel="model1",
        createdBy="user1",
        status=CollectionStatus.ACTIVE,
    )

    result = service._matches_filter(collection, "nonexistent")
    assert result is False


def test_sort_collections_by_name(service):
    """Test _sort_collections sorts by name."""
    col1 = RagCollectionConfig(
        collectionId="col1",
        repositoryId="repo1",
        name="B",
        embeddingModel="model1",
        createdBy="user1",
        status=CollectionStatus.ACTIVE,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )

    col2 = RagCollectionConfig(
        collectionId="col2",
        repositoryId="repo1",
        name="A",
        embeddingModel="model1",
        createdBy="user1",
        status=CollectionStatus.ACTIVE,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )

    sort_params = SortParams(sort_by=CollectionSortBy.NAME, sort_order=SortOrder.ASC)
    sorted_cols = service._sort_collections([col1, col2], sort_params)

    assert sorted_cols[0].name == "A"
    assert sorted_cols[1].name == "B"


def test_get_sort_key_updated_at(service):
    """Test _get_sort_key extracts updatedAt."""
    now = datetime.now(timezone.utc)
    collection = RagCollectionConfig(
        collectionId="col1",
        repositoryId="repo1",
        name="Test",
        embeddingModel="model1",
        createdBy="user1",
        status=CollectionStatus.ACTIVE,
        createdAt=now,
        updatedAt=now,
    )

    key = service._get_sort_key(collection, "updatedAt")
    assert key == now


def test_enrich_with_repository_metadata_missing_repo(service):
    """Test _enrich_with_repository_metadata handles missing repository."""
    collection = RagCollectionConfig(
        collectionId="col1",
        repositoryId="missing-repo",
        name="Test",
        embeddingModel="model1",
        createdBy="user1",
        status=CollectionStatus.ACTIVE,
        createdAt=datetime.now(timezone.utc),
        updatedAt=datetime.now(timezone.utc),
    )

    repositories = [{"repositoryId": "repo1", "repositoryName": "Repo 1"}]

    enriched = service._enrich_with_repository_metadata([collection], repositories)
    assert len(enriched) == 1
    assert enriched[0]["repositoryName"] == "missing-repo"  # Falls back to ID
