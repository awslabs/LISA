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

# Set up required environment variables before imports
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
os.environ.setdefault("AWS_SESSION_TOKEN", "testing")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("LISA_INGESTION_JOB_TABLE_NAME", "ingestion-job-table")
os.environ.setdefault("REPOSITORY_TABLE", "repository-table")
os.environ.setdefault("VECTOR_STORE_TABLE", "vector-store-table")
os.environ.setdefault("RAG_DOCUMENT_TABLE", "rag-document-table")
os.environ.setdefault("RAG_SUB_DOCUMENT_TABLE", "rag-sub-document-table")
os.environ.setdefault("LISA_RAG_VECTOR_STORE_TABLE", "vector-store-table")
os.environ.setdefault("BEDROCK_REGION", "us-east-1")

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from repository.lambda_functions import _similarity_search, _similarity_search_with_score, delete_index
from utilities.repository_types import RepositoryType


@pytest.fixture
def mock_similarity_common(aws_env_vars):
    """Common mocks for similarity function tests."""
    additional_env_vars = {
        "REPOSITORY_TABLE": "repository-table",
        "BEDROCK_REGION": "us-east-1",
        "LISA_INGESTION_JOB_TABLE_NAME": "ingestion-job-table",
        "VECTOR_STORE_TABLE": "vector-store-table",
        "RAG_DOCUMENT_TABLE": "rag-document-table",
        "RAG_SUB_DOCUMENT_TABLE": "rag-sub-document-table",
        "LISA_RAG_VECTOR_STORE_TABLE": "vector-store-table",
    }

    with patch.dict(os.environ, additional_env_vars, clear=False):
        yield


def test_similarity_search():
    """Test _similarity_search function"""
    # Mock vector store
    mock_vs = MagicMock()
    mock_doc = MagicMock()
    mock_doc.page_content = "Test content"
    mock_doc.metadata = {"source": "test.txt"}
    mock_vs.similarity_search_with_score.return_value = [(mock_doc, 0.8)]

    result = _similarity_search(mock_vs, "test query", 5)

    assert len(result) == 1
    assert result[0]["page_content"] == "Test content"
    assert result[0]["metadata"] == {"source": "test.txt"}
    mock_vs.similarity_search_with_score.assert_called_once_with("test query", k=5)


def test_similarity_search_with_score_pgvector():
    """Test _similarity_search_with_score with PGVector repository"""
    # Mock vector store and repository
    mock_vs = MagicMock()
    mock_doc = MagicMock()
    mock_doc.page_content = "Test content"
    mock_doc.metadata = {"source": "test.txt"}
    mock_vs.similarity_search_with_score.return_value = [(mock_doc, 0.8)]  # cosine distance

    repository = {"type": "pgvector"}

    with patch("repository.lambda_functions.RepositoryType.is_type") as mock_is_type:
        mock_is_type.return_value = True

        result = _similarity_search_with_score(mock_vs, "test query", 3, repository)

        assert len(result) == 1
        assert result[0]["page_content"] == "Test content"
        assert result[0]["metadata"]["source"] == "test.txt"
        assert result[0]["metadata"]["similarity_score"] == 0.6  # 1 - (0.8/2)


def test_similarity_search_with_score_opensearch():
    """Test _similarity_search_with_score with OpenSearch repository"""
    # Mock vector store and repository
    mock_vs = MagicMock()
    mock_doc = MagicMock()
    mock_doc.page_content = "Test content"
    mock_doc.metadata = {"source": "test.txt"}
    mock_vs.similarity_search_with_score.return_value = [(mock_doc, 0.9)]  # similarity score

    repository = {"type": "opensearch"}

    with patch("repository.lambda_functions.RepositoryType.is_type") as mock_is_type:
        mock_is_type.return_value = False  # Not PGVector

        result = _similarity_search_with_score(mock_vs, "test query", 3, repository)

        assert len(result) == 1
        assert result[0]["page_content"] == "Test content"
        assert result[0]["metadata"]["similarity_score"] == 0.9  # Direct similarity score


def test_delete_index_opensearch(mock_similarity_common, lambda_context):
    """Test delete_index with OpenSearch repository"""
    event = {
        "pathParameters": {"repositoryId": "test-repo", "modelName": "test-model"},
        "requestContext": {"authorizer": {"groups": "[]"}},
        "headers": {"authorization": "Bearer test-token"},
    }

    with patch("repository.lambda_functions.vs_repo.find_repository_by_id") as mock_find_repo, patch(
        "repository.lambda_functions.get_vector_store_client"
    ) as mock_get_vs, patch("repository.lambda_functions.RepositoryType.is_type") as mock_is_type, patch(
        "repository.lambda_functions.is_admin"
    ) as mock_is_admin, patch(
        "utilities.auth.is_admin"
    ) as mock_auth_is_admin, patch(
        "utilities.auth.get_groups"
    ) as mock_get_groups, patch(
        "utilities.auth.get_username"
    ) as mock_get_username, patch(
        "repository.lambda_functions.RagEmbeddings"
    ):

        # Set up authentication mocks
        mock_is_admin.return_value = True
        mock_auth_is_admin.return_value = True
        mock_get_groups.return_value = ["admin"]
        mock_get_username.return_value = "test-user"

        # Set up repository mocks
        mock_find_repo.return_value = {"type": "opensearch", "allowedGroups": ["admin"]}
        mock_vs = MagicMock()
        mock_vs.client.indices.exists.return_value = True
        mock_get_vs.return_value = mock_vs
        mock_is_type.side_effect = lambda _, repo_type: repo_type == RepositoryType.OPENSEARCH

        delete_index(event, lambda_context)

        mock_vs.client.indices.exists.assert_called_once_with(index="test-model")
        mock_vs.client.indices.delete.assert_called_once_with(index="test-model")


def test_delete_index_exception(mock_similarity_common, lambda_context):
    """Test delete_index handles exceptions"""
    event = {
        "pathParameters": {"repositoryId": "test-repo", "modelName": "test-model"},
        "requestContext": {"authorizer": {"groups": "[]"}},
    }

    with patch("repository.lambda_functions.vs_repo.find_repository_by_id") as mock_find_repo, patch(
        "repository.lambda_functions.get_vector_store_client"
    ) as mock_get_vs, patch("repository.lambda_functions.RepositoryType.is_type") as mock_is_type, patch(
        "repository.lambda_functions.is_admin"
    ) as mock_is_admin, patch(
        "repository.lambda_functions.RagEmbeddings"
    ):

        mock_is_admin.return_value = True
        mock_find_repo.return_value = {"type": "opensearch"}
        mock_vs = MagicMock()
        mock_vs.client.indices.exists.side_effect = Exception("Connection error")
        mock_get_vs.return_value = mock_vs
        mock_is_type.side_effect = lambda _, repo_type: repo_type == RepositoryType.OPENSEARCH

        # Should not raise exception
        delete_index(event, lambda_context)
