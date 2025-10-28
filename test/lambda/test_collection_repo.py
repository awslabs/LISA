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

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))


@pytest.fixture
def mock_dynamodb_table():
    return MagicMock()


@pytest.fixture
def collection_repo(mock_dynamodb_table, monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("LISA_RAG_COLLECTIONS_TABLE", "test-table")

    with patch("boto3.resource") as mock_resource:
        mock_resource.return_value.Table.return_value = mock_dynamodb_table
        from repository.collection_repo import CollectionRepository

        return CollectionRepository()


def test_delete_collection(collection_repo, mock_dynamodb_table):
    result = collection_repo.delete("coll1", "repo1")
    assert result is True
    mock_dynamodb_table.delete_item.assert_called_once()


def test_count_by_repository(collection_repo, mock_dynamodb_table):
    mock_dynamodb_table.query.return_value = {"Count": 5}

    count = collection_repo.count_by_repository("repo1")
    assert count == 5


# Additional coverage tests
def test_collection_repo_create(collection_repo, mock_dynamodb_table):
    from models.domain_objects import CollectionStatus, RagCollectionConfig

    collection = RagCollectionConfig(
        collectionId="col1",
        repositoryId="repo1",
        name="Test",
        status=CollectionStatus.ACTIVE,
        createdBy="user1",
        embeddingModel="model1",
    )

    result = collection_repo.create(collection)
    assert result.collectionId == "col1"
    mock_dynamodb_table.put_item.assert_called_once()


def test_collection_repo_find_by_id(collection_repo, mock_dynamodb_table):
    mock_dynamodb_table.get_item.return_value = {
        "Item": {
            "collectionId": "col1",
            "repositoryId": "repo1",
            "name": "Test",
            "status": "ACTIVE",
            "createdBy": "user1",
            "embeddingModel": "model1",
        }
    }

    result = collection_repo.find_by_id("col1", "repo1")
    assert result.collectionId == "col1"


def test_collection_repo_find_by_id_not_found(collection_repo, mock_dynamodb_table):
    mock_dynamodb_table.get_item.return_value = {}

    result = collection_repo.find_by_id("col1", "repo1")
    assert result is None


def test_collection_repo_update(collection_repo, mock_dynamodb_table):
    mock_dynamodb_table.update_item.return_value = {
        "Attributes": {
            "collectionId": "col1",
            "repositoryId": "repo1",
            "name": "Updated",
            "status": "ACTIVE",
            "createdBy": "user1",
            "embeddingModel": "model1",
        }
    }

    result = collection_repo.update("col1", "repo1", {"name": "Updated"})
    assert result.name == "Updated"


def test_collection_repo_update_error(collection_repo, mock_dynamodb_table):
    from botocore.exceptions import ClientError
    from repository.collection_repo import CollectionRepositoryError

    mock_dynamodb_table.update_item.side_effect = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem"
    )

    with pytest.raises(CollectionRepositoryError):
        collection_repo.update("col1", "repo1", {"name": "Updated"})


def test_collection_repo_update_no_valid_fields(collection_repo):
    from repository.collection_repo import CollectionRepositoryError

    with pytest.raises(CollectionRepositoryError):
        collection_repo.update("col1", "repo1", {"collectionId": "new_id", "repositoryId": "new_repo"})


def test_collection_repo_update_with_expected_version_conflict(collection_repo, mock_dynamodb_table):
    from botocore.exceptions import ClientError
    from repository.collection_repo import CollectionRepositoryError

    mock_dynamodb_table.update_item.side_effect = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException"}}, "UpdateItem"
    )

    with pytest.raises(CollectionRepositoryError, match="modified by another process"):
        collection_repo.update("col1", "repo1", {"name": "Updated"}, expected_version="old_version")


def test_collection_repo_delete_error(collection_repo, mock_dynamodb_table):
    from botocore.exceptions import ClientError
    from repository.collection_repo import CollectionRepositoryError

    mock_dynamodb_table.delete_item.side_effect = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException"}}, "DeleteItem"
    )

    with pytest.raises(CollectionRepositoryError):
        collection_repo.delete("col1", "repo1")


def test_collection_repo_list_by_repository(collection_repo, mock_dynamodb_table):
    mock_dynamodb_table.query.return_value = {
        "Items": [
            {
                "collectionId": "col1",
                "repositoryId": "repo1",
                "name": "Test",
                "status": "ACTIVE",
                "createdBy": "user1",
                "embeddingModel": "model1",
            }
        ]
    }

    collections, next_key = collection_repo.list_by_repository("repo1")
    assert len(collections) == 1


def test_collection_repo_list_with_filters(collection_repo, mock_dynamodb_table):
    from models.domain_objects import CollectionSortBy, CollectionStatus, SortOrder

    mock_dynamodb_table.query.return_value = {
        "Items": [
            {
                "collectionId": "col1",
                "repositoryId": "repo1",
                "name": "Test",
                "status": "ACTIVE",
                "createdBy": "user1",
                "embeddingModel": "model1",
            }
        ]
    }

    collections, next_key = collection_repo.list_by_repository(
        "repo1", status_filter=CollectionStatus.ACTIVE, sort_by=CollectionSortBy.NAME, sort_order=SortOrder.ASC
    )
    assert len(collections) == 1


def test_collection_repo_list_with_text_filter(collection_repo, mock_dynamodb_table):
    mock_dynamodb_table.query.return_value = {
        "Items": [
            {
                "collectionId": "col1",
                "repositoryId": "repo1",
                "name": "Test Collection",
                "description": "A test",
                "status": "ACTIVE",
                "createdBy": "user1",
                "embeddingModel": "model1",
            }
        ]
    }

    collections, next_key = collection_repo.list_by_repository("repo1", filter_text="test")
    assert len(collections) == 1


def test_collection_repo_list_with_sort_by_updated_at(collection_repo, mock_dynamodb_table):
    from models.domain_objects import CollectionSortBy, SortOrder

    mock_dynamodb_table.query.return_value = {
        "Items": [
            {
                "collectionId": "col1",
                "repositoryId": "repo1",
                "name": "Test1",
                "status": "ACTIVE",
                "createdBy": "user1",
                "embeddingModel": "model1",
                "updatedAt": "2024-01-02T00:00:00Z",
            },
            {
                "collectionId": "col2",
                "repositoryId": "repo1",
                "name": "Test2",
                "status": "ACTIVE",
                "createdBy": "user1",
                "embeddingModel": "model1",
                "updatedAt": "2024-01-01T00:00:00Z",
            },
        ]
    }

    collections, _ = collection_repo.list_by_repository(
        "repo1", sort_by=CollectionSortBy.UPDATED_AT, sort_order=SortOrder.DESC
    )
    assert len(collections) == 2


def test_collection_repo_find_by_name(collection_repo, mock_dynamodb_table):
    mock_dynamodb_table.query.return_value = {
        "Items": [
            {
                "collectionId": "col1",
                "repositoryId": "repo1",
                "name": "Test",
                "status": "ACTIVE",
                "createdBy": "user1",
                "embeddingModel": "model1",
            }
        ]
    }

    result = collection_repo.find_by_name("repo1", "Test")
    assert result.name == "Test"


def test_collection_repo_find_by_name_not_found(collection_repo, mock_dynamodb_table):
    mock_dynamodb_table.query.return_value = {"Items": []}

    result = collection_repo.find_by_name("repo1", "Test")
    assert result is None


def test_collection_repo_create_error(collection_repo, mock_dynamodb_table):
    from botocore.exceptions import ClientError
    from models.domain_objects import CollectionStatus, RagCollectionConfig
    from repository.collection_repo import CollectionRepositoryError

    mock_dynamodb_table.put_item.side_effect = ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException"}}, "PutItem"
    )

    collection = RagCollectionConfig(
        collectionId="col1",
        repositoryId="repo1",
        name="Test",
        status=CollectionStatus.ACTIVE,
        createdBy="user1",
        embeddingModel="model1",
    )

    with pytest.raises(CollectionRepositoryError):
        collection_repo.create(collection)


def test_collection_repo_update_with_version(collection_repo, mock_dynamodb_table):
    mock_dynamodb_table.update_item.return_value = {
        "Attributes": {
            "collectionId": "col1",
            "repositoryId": "repo1",
            "name": "Updated",
            "status": "ACTIVE",
            "createdBy": "user1",
            "embeddingModel": "model1",
            "updatedAt": "2024-01-01T00:00:00Z",
        }
    }

    result = collection_repo.update("col1", "repo1", {"name": "Updated"}, expected_version="2024-01-01T00:00:00Z")
    assert result.name == "Updated"
