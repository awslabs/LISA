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

# Set up mock AWS credentials
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from repository.lambda_functions import _similarity_search, _similarity_search_with_score, clear_vector_store
from utilities.repository_types import RepositoryType


def test_similarity_search():
    """Test _similarity_search function"""
    # Mock vector store
    mock_vs = MagicMock()
    mock_doc = MagicMock()
    mock_doc.page_content = "Test content"
    mock_doc.metadata = {"source": "test.txt"}
    mock_vs.similarity_search_with_score.return_value = [mock_doc]
    
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


def test_clear_vector_store_opensearch():
    """Test clear_vector_store with OpenSearch repository"""
    mock_vs = MagicMock()
    mock_vs.client.indices.exists.return_value = True
    mock_vs.client.indices.delete.return_value = {}
    
    repository = {"type": "opensearch"}
    
    with patch("repository.lambda_functions.RepositoryType.is_type") as mock_is_type:
        mock_is_type.side_effect = lambda repo, repo_type: repo_type == RepositoryType.OPENSEARCH
        
        clear_vector_store(repository, mock_vs, "test-model")
        
        mock_vs.client.indices.exists.assert_called_once_with(index="test-model")
        mock_vs.client.indices.delete.assert_called_once_with(index="test-model")


def test_clear_vector_store_opensearch_index_not_exists():
    """Test clear_vector_store with OpenSearch when index doesn't exist"""
    mock_vs = MagicMock()
    mock_vs.client.indices.exists.return_value = False
    
    repository = {"type": "opensearch"}
    
    with patch("repository.lambda_functions.RepositoryType.is_type") as mock_is_type:
        mock_is_type.side_effect = lambda repo, repo_type: repo_type == RepositoryType.OPENSEARCH
        
        clear_vector_store(repository, mock_vs, "test-model")
        
        mock_vs.client.indices.exists.assert_called_once_with(index="test-model")
        mock_vs.client.indices.delete.assert_not_called()


def test_clear_vector_store_pgvector():
    """Test clear_vector_store with PGVector repository"""
    mock_vs = MagicMock()
    mock_vs.delete_collection.return_value = None
    
    repository = {"type": "pgvector"}
    
    with patch("repository.lambda_functions.RepositoryType.is_type") as mock_is_type:
        mock_is_type.side_effect = lambda repo, repo_type: repo_type == RepositoryType.PGVECTOR
        
        clear_vector_store(repository, mock_vs, "test-model")
        
        mock_vs.delete_collection.assert_called_once()


def test_clear_vector_store_exception():
    """Test clear_vector_store handles exceptions"""
    mock_vs = MagicMock()
    mock_vs.client.indices.exists.side_effect = Exception("Connection error")
    
    repository = {"type": "opensearch"}
    
    with patch("repository.lambda_functions.RepositoryType.is_type") as mock_is_type:
        mock_is_type.side_effect = lambda repo, repo_type: repo_type == RepositoryType.OPENSEARCH
        
        # Should not raise exception
        clear_vector_store(repository, mock_vs, "test-model")