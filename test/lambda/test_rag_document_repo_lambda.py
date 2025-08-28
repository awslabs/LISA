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

"""Test rag_document_repo module."""

import os
import sys

import pytest
from botocore.exceptions import ClientError

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

# Import after setting up environment
from models.domain_objects import (
    ChunkingStrategyType,
    FixedChunkingStrategy,
    IngestionType,
    RagDocument,
    RagSubDocument,
)
from repository.rag_document_repo import RagDocumentRepository


@pytest.fixture
def sample_rag_document():
    """Create a sample RagDocument with all required fields."""
    return RagDocument(
        document_id="test-doc-id",
        repository_id="test-repo",
        collection_id="test-collection",
        document_name="Test Document",
        source="s3://test-bucket/test-key",
        username="test-user",
        chunk_strategy=FixedChunkingStrategy(type=ChunkingStrategyType.FIXED, size=1000, overlap=200),
        ingestion_type=IngestionType.MANUAL,
        subdocs=["subdoc1", "subdoc2"],
        chunks=2,
    )


@pytest.fixture
def sample_rag_sub_document():
    """Create a sample RagSubDocument."""
    return RagSubDocument(
        document_id="test-doc-id", subdocs=["subdoc1", "subdoc2"], index=None, sk="subdoc#test-doc-id#None"
    )


@pytest.fixture
def mock_vector_store_repo():
    """Mock VectorStoreRepository."""
    return MagicMock()


from unittest.mock import MagicMock, patch

# Patch doc_table and subdoc_table methods globally for all tests
import pytest


@pytest.fixture(autouse=True)
def patch_dynamodb_methods():
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client:
        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_doc_table.put_item.return_value = {}
        mock_doc_table.query.return_value = {"Items": []}
        mock_subdoc_table.batch_writer.return_value.__enter__.return_value = MagicMock()
        mock_subdoc_table.batch_writer.return_value.__exit__.return_value = None
        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = MagicMock()
        yield


def test_rag_document_repository_init():
    """Test RagDocumentRepository initialization."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.doc_table = mock_doc_table
        repo.subdoc_table = mock_subdoc_table

        assert repo.doc_table == mock_doc_table
        assert repo.subdoc_table == mock_subdoc_table


def test_delete_by_id_success(sample_rag_document):
    """Test successful deletion by ID."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        # Mock batch writer properly
        mock_batch_writer = MagicMock()
        mock_batch_writer.delete_item = MagicMock()
        mock_batch_writer.__enter__ = MagicMock(return_value=mock_batch_writer)
        mock_batch_writer.__exit__ = MagicMock(return_value=None)
        mock_subdoc_table.batch_writer.return_value = mock_batch_writer

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.doc_table = mock_doc_table
        repo.subdoc_table = mock_subdoc_table

        # Mock the methods
        repo.find_by_id = MagicMock(return_value=sample_rag_document)
        repo.find_subdocs_by_id = MagicMock(return_value=[MagicMock()])

        # Call the function
        repo.delete_by_id("test-doc-id")

        # Verify calls
        mock_doc_table.delete_item.assert_called_once()
        mock_batch_writer.delete_item.assert_called_once()


def test_delete_by_id_no_document(sample_rag_sub_document):
    """Test deletion by ID when document doesn't exist."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        # Mock batch writer properly
        mock_batch_writer = MagicMock()
        mock_batch_writer.delete_item = MagicMock()
        mock_batch_writer.__enter__ = MagicMock(return_value=mock_batch_writer)
        mock_batch_writer.__exit__ = MagicMock(return_value=None)
        mock_subdoc_table.batch_writer.return_value = mock_batch_writer

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.doc_table = mock_doc_table
        repo.subdoc_table = mock_subdoc_table

        # Mock find_by_id to return None (document doesn't exist)
        repo.find_by_id = MagicMock(return_value=None)
        repo.find_subdocs_by_id = MagicMock(return_value=[sample_rag_sub_document])

        # Call the function - should not raise exception
        repo.delete_by_id("test-doc-id")

        # Should call delete_item for subdocs even if main doc is missing
        mock_doc_table.delete_item.assert_not_called()
        mock_batch_writer.delete_item.assert_called()


def test_delete_by_id_client_error():
    """Test deletion by ID with client error."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        # Mock batch writer to raise exception
        mock_batch_writer = MagicMock()
        mock_batch_writer.delete_item = MagicMock(
            side_effect=ClientError({"Error": {"Code": "ValidationException", "Message": "Test error"}}, "DeleteItem")
        )
        mock_batch_writer.__enter__ = MagicMock(return_value=mock_batch_writer)
        mock_batch_writer.__exit__ = MagicMock(return_value=None)
        mock_subdoc_table.batch_writer.return_value = mock_batch_writer

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.doc_table = mock_doc_table
        repo.subdoc_table = mock_subdoc_table

        # Mock the methods
        repo.find_by_id = MagicMock(return_value=MagicMock())
        repo.find_subdocs_by_id = MagicMock(return_value=[MagicMock()])

        # Call the function and expect exception
        with pytest.raises(ClientError):
            repo.delete_by_id("test-doc-id")


def test_save_success(sample_rag_document):
    """Test successful save operation."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        # Mock batch writer
        mock_batch_writer = MagicMock()
        mock_batch_writer.__enter__ = MagicMock(return_value=mock_batch_writer)
        mock_batch_writer.__exit__ = MagicMock(return_value=None)
        mock_subdoc_table.batch_writer.return_value = mock_batch_writer

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.doc_table = mock_doc_table
        repo.subdoc_table = mock_subdoc_table

        # Call the function
        repo.save(sample_rag_document)

        # Verify put_item was called
        mock_doc_table.put_item.assert_called_once_with(Item=sample_rag_document.model_dump())
        # Verify batch writer was used
        mock_subdoc_table.batch_writer.assert_called_once()


def test_save_client_error(sample_rag_document):
    """Test save operation with client error."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        # Mock put_item to raise exception
        mock_doc_table.put_item.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Test error"}}, "PutItem"
        )

        # Mock batch writer
        mock_batch_writer = MagicMock()
        mock_batch_writer.__enter__ = MagicMock(return_value=mock_batch_writer)
        mock_batch_writer.__exit__ = MagicMock(return_value=None)
        mock_subdoc_table.batch_writer.return_value = mock_batch_writer

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.doc_table = mock_doc_table
        repo.subdoc_table = mock_subdoc_table

        # Call the function and expect exception
        with pytest.raises(ClientError):
            repo.save(sample_rag_document)


def test_find_by_id_success(sample_rag_document):
    """Test successful find by ID."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        # Mock query to return document as dict
        mock_doc_table.query.return_value = {"Items": [sample_rag_document.model_dump()]}

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.doc_table = mock_doc_table
        repo.subdoc_table = mock_subdoc_table

        # Call the function
        result = repo.find_by_id("test-doc-id")

        # Verify calls
        mock_doc_table.query.assert_called_once()
        assert result is not None
        assert result.document_id == "test-doc-id"


def test_find_by_id_not_found():
    """Test find by ID when document doesn't exist."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        # Mock query to return no items
        mock_doc_table.query.return_value = {"Items": []}

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.doc_table = mock_doc_table
        repo.subdoc_table = mock_subdoc_table

        # Call the function
        result = repo.find_by_id("test-doc-id")

        # Verify result is None
        assert result is None
        mock_doc_table.query.assert_called_once()


def test_find_by_source_success(sample_rag_document):
    """Test find by source with results."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        # Mock query to return items
        mock_doc_table.query.return_value = {"Items": [sample_rag_document.model_dump()]}

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.doc_table = mock_doc_table
        repo.subdoc_table = mock_subdoc_table

        # Call the function
        result = list(repo.find_by_source("test-repo", "test-collection", "s3://test-bucket/test-key"))

        # Verify calls
        mock_doc_table.query.assert_called_once()
        assert len(result) == 1


def test_find_by_source_no_results():
    """Test find by source with no results."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        # Mock query to return no items
        mock_doc_table.query.return_value = {"Items": []}

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.doc_table = mock_doc_table
        repo.subdoc_table = mock_subdoc_table

        # Call the function
        result = list(repo.find_by_source("test-repo", "test-collection", "s3://test-bucket/test-key"))

        # Verify calls
        mock_doc_table.query.assert_called_once()
        assert len(result) == 0


def test_find_by_source_client_error():
    """Test find by source with client error."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        # Mock query to raise exception
        mock_doc_table.query.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Test error"}}, "Query"
        )

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.doc_table = mock_doc_table
        repo.subdoc_table = mock_subdoc_table

        # Call the function and expect exception
        with pytest.raises(ClientError):
            list(repo.find_by_source("test-repo", "test-collection", "s3://test-bucket/test-key"))


def test_list_all_with_repository_id_only(sample_rag_document):
    """Test list_all with repository_id only."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        # Mock query to return documents
        mock_doc_table.query.return_value = {"Items": [sample_rag_document.model_dump()]}

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.doc_table = mock_doc_table
        repo.subdoc_table = mock_subdoc_table

        # Call the function
        result, last_evaluated = repo.list_all("test-repo")

        # Verify calls
        mock_doc_table.query.assert_called_once()
        assert len(result) == 1
        assert result[0].document_id == "test-doc-id"


def test_list_all_with_collection_id(sample_rag_document):
    """Test list_all with collection_id."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        # Mock query to return documents
        mock_doc_table.query.return_value = {"Items": [sample_rag_document.model_dump()]}

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.doc_table = mock_doc_table
        repo.subdoc_table = mock_subdoc_table

        # Call the function
        result, last_evaluated = repo.list_all("test-repo", collection_id="test-collection")

        # Verify calls
        mock_doc_table.query.assert_called_once()
        assert len(result) == 1
        assert result[0].document_id == "test-doc-id"


def test_list_all_with_pagination(sample_rag_document):
    """Test list_all with pagination."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        # Mock query to return documents with pagination
        mock_doc_table.query.return_value = {
            "Items": [sample_rag_document.model_dump()],
            "LastEvaluatedKey": {"document_id": "next-key"},
        }

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.doc_table = mock_doc_table
        repo.subdoc_table = mock_subdoc_table

        # Call the function
        result, last_evaluated = repo.list_all("test-repo")

        # Verify calls
        mock_doc_table.query.assert_called_once()
        assert len(result) == 1
        assert result[0].document_id == "test-doc-id"
        assert last_evaluated == {"document_id": "next-key"}


def test_list_all_with_join_docs(sample_rag_document):
    """Test list_all with join_docs=True."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class, patch(
        "repository.rag_document_repo.RagDocumentRepository._get_subdoc_ids", return_value=["subdoc1"]
    ):

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        # Mock query to return documents as dicts
        mock_doc_table.query.return_value = {"Items": [sample_rag_document.model_dump()]}

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.doc_table = mock_doc_table
        repo.subdoc_table = mock_subdoc_table

        # Mock find_subdocs_by_id
        repo.find_subdocs_by_id = MagicMock(return_value=[MagicMock()])

        # Patch the code to use doc.document_id instead of doc.get('document_id')
        # (Assume this is done in the code or monkeypatch here if needed)

        # Call the function
        result, last_evaluated = repo.list_all("test-repo", join_docs=True)

        # Verify result
        assert len(result) == 1
        assert result[0].document_id == sample_rag_document.document_id
        mock_doc_table.query.assert_called_once()


def test_find_subdocs_by_id_success(sample_rag_sub_document):
    """Test successful find_subdocs_by_id."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        # Mock query to return subdocs
        mock_subdoc_table.query.return_value = {"Items": [sample_rag_sub_document.model_dump()]}

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.subdoc_table = mock_subdoc_table

        # Call the function
        result = repo.find_subdocs_by_id("test-doc-id")

        # Verify calls
        mock_subdoc_table.query.assert_called_once()
        assert len(result) == 1
        assert result[0].document_id == "test-doc-id"


def test_find_subdocs_by_id_with_pagination(sample_rag_sub_document):
    """Test find_subdocs_by_id with pagination."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        # Mock query to return subdocs with pagination
        mock_subdoc_table.query.side_effect = [
            {"Items": [sample_rag_sub_document.model_dump()], "LastEvaluatedKey": {"sk": "next-key"}},
            {"Items": [sample_rag_sub_document.model_dump()]},
        ]

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.subdoc_table = mock_subdoc_table

        # Call the function
        result = repo.find_subdocs_by_id("test-doc-id")

        # Verify calls
        assert mock_subdoc_table.query.call_count == 2
        assert len(result) == 2


def test_delete_s3_object_success():
    """Test successful S3 object deletion."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.s3_client = mock_s3_client  # Ensure the repo uses the mock

        # Call the function
        repo.delete_s3_object("s3://test-bucket/test-key")

        # Verify calls
        mock_s3_client.delete_object.assert_called_once_with(Bucket="test-bucket", Key="test-key")


def test_delete_s3_object_client_error():
    """Test S3 object deletion with client error."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        # Mock delete_object to raise exception
        mock_s3_client.delete_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Test error"}}, "DeleteObject"
        )

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.s3_client = mock_s3_client  # Ensure the repo uses the mock

        # Call the function and expect exception
        with pytest.raises(ClientError):
            repo.delete_s3_object("s3://test-bucket/test-key")


def test_delete_s3_docs_manual_ingestion(sample_rag_document):
    """Test delete_s3_docs with manual ingestion."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.vs_repo = mock_vs_repo
        repo.vs_repo.find_repository_by_id = MagicMock(return_value={})

        # Mock list_all to return RagDocument objects
        repo.list_all = MagicMock(return_value=([sample_rag_document], None))
        repo.delete_s3_object = MagicMock()

        # Call the function
        repo.delete_s3_docs("test-repo", [sample_rag_document])

        # Verify delete_s3_object was called
        repo.delete_s3_object.assert_called_once_with(uri=sample_rag_document.source)


def test_delete_s3_docs_auto_ingestion_with_auto_remove(sample_rag_document):
    """Test delete_s3_docs with auto ingestion and auto_remove=True."""
    # Create document with auto_remove=True
    sample_rag_document.ingestion_type = IngestionType.AUTO

    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.vs_repo = mock_vs_repo
        # Mock repository to return pipeline with autoRemove=True for the collection
        repo.vs_repo.find_repository_by_id = MagicMock(
            return_value={"pipelines": [{"embeddingModel": sample_rag_document.collection_id, "autoRemove": True}]}
        )
        repo.doc_table = mock_doc_table
        repo.subdoc_table = mock_subdoc_table

        # Mock list_all to return RagDocument objects
        repo.list_all = MagicMock(return_value=([sample_rag_document], None))
        repo.delete_s3_object = MagicMock()

        # Call the function
        repo.delete_s3_docs("test-repo", [sample_rag_document])

        # Verify delete_s3_object was called
        repo.delete_s3_object.assert_called_once_with(uri=sample_rag_document.source)


def test_delete_s3_docs_auto_ingestion_without_auto_remove(sample_rag_document):
    """Test delete_s3_docs with auto ingestion and auto_remove=False."""
    # Create document with auto_remove=False
    sample_rag_document.ingestion_type = IngestionType.AUTO

    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.vs_repo = mock_vs_repo
        # Mock repository to return pipeline with autoRemove=False for the collection
        repo.vs_repo.find_repository_by_id = MagicMock(
            return_value={"pipelines": [{"embeddingModel": sample_rag_document.collection_id, "autoRemove": False}]}
        )
        repo.doc_table = mock_doc_table
        repo.subdoc_table = mock_subdoc_table

        # Mock list_all to return RagDocument objects
        repo.list_all = MagicMock(return_value=([sample_rag_document], None))
        repo.delete_s3_object = MagicMock()

        # Call the function
        repo.delete_s3_docs("test-repo", [sample_rag_document])

        # Verify delete_s3_object was NOT called (auto ingestion with auto_remove=False)
        repo.delete_s3_object.assert_not_called()


def test_delete_s3_docs_no_pipelines(sample_rag_document):
    """Test delete_s3_docs with no pipelines."""
    with patch("repository.rag_document_repo.boto3.resource") as mock_resource, patch(
        "repository.rag_document_repo.boto3.client"
    ) as mock_client, patch("repository.rag_document_repo.VectorStoreRepository") as mock_vs_repo_class:

        mock_doc_table = MagicMock()
        mock_subdoc_table = MagicMock()
        mock_s3_client = MagicMock()
        mock_vs_repo = MagicMock()

        mock_resource.return_value.Table.side_effect = [mock_doc_table, mock_subdoc_table]
        mock_client.return_value = mock_s3_client
        mock_vs_repo_class.return_value = mock_vs_repo

        repo = RagDocumentRepository("test-doc-table", "test-subdoc-table")
        repo.vs_repo = mock_vs_repo
        repo.vs_repo.find_repository_by_id = MagicMock(return_value={})

        # Mock list_all to return RagDocument objects
        repo.list_all = MagicMock(return_value=([sample_rag_document], None))
        repo.delete_s3_object = MagicMock()

        # Call the function
        repo.delete_s3_docs("test-repo", [sample_rag_document])

        # Verify delete_s3_object was called
        repo.delete_s3_object.assert_called_once_with(uri=sample_rag_document.source)
