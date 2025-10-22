#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import sys
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

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
