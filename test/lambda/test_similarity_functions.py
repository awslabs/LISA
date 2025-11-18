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

# Set up mock AWS credentials
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from repository.services.opensearch_repository_service import OpenSearchRepositoryService
from repository.services.pgvector_repository_service import PGVectorRepositoryService


def test_opensearch_retrieve_documents_without_score():
    """Test OpenSearch retrieve_documents without scores"""
    repository = {"repositoryId": "test-repo", "type": "opensearch"}
    service = OpenSearchRepositoryService(repository)

    # Mock vector store
    mock_vs = MagicMock()
    mock_doc = MagicMock()
    mock_doc.page_content = "Test content"
    mock_doc.metadata = {"source": "test.txt"}
    mock_vs.similarity_search_with_score.return_value = [(mock_doc, 0.8)]

    with patch("repository.services.vector_store_repository_service.RagEmbeddings"):
        with patch("repository.services.vector_store_repository_service.get_vector_store_client", return_value=mock_vs):
            result = service.retrieve_documents("test query", "test-collection", 5, include_score=False)

    assert len(result) == 1
    assert result[0]["page_content"] == "Test content"
    assert result[0]["metadata"] == {"source": "test.txt"}
    assert "similarity_score" not in result[0]["metadata"]
    mock_vs.similarity_search_with_score.assert_called_once_with("test query", k=5)


def test_pgvector_retrieve_documents_with_score():
    """Test PGVector retrieve_documents with score normalization"""
    repository = {"repositoryId": "test-repo", "type": "pgvector"}
    service = PGVectorRepositoryService(repository)

    # Mock vector store
    mock_vs = MagicMock()
    mock_doc = MagicMock()
    mock_doc.page_content = "Test content"
    mock_doc.metadata = {"source": "test.txt"}
    mock_vs.similarity_search_with_score.return_value = [(mock_doc, 0.8)]  # cosine distance

    with patch("repository.services.vector_store_repository_service.RagEmbeddings"):
        with patch("repository.services.vector_store_repository_service.get_vector_store_client", return_value=mock_vs):
            result = service.retrieve_documents("test query", "test-collection", 3, include_score=True)

    assert len(result) == 1
    assert result[0]["page_content"] == "Test content"
    assert result[0]["metadata"]["source"] == "test.txt"
    assert result[0]["metadata"]["similarity_score"] == 0.6  # 1 - (0.8/2)


def test_opensearch_retrieve_documents_with_score():
    """Test OpenSearch retrieve_documents with score"""
    repository = {"repositoryId": "test-repo", "type": "opensearch"}
    service = OpenSearchRepositoryService(repository)

    # Mock vector store
    mock_vs = MagicMock()
    mock_doc = MagicMock()
    mock_doc.page_content = "Test content"
    mock_doc.metadata = {"source": "test.txt"}
    mock_vs.similarity_search_with_score.return_value = [(mock_doc, 0.9)]  # similarity score

    with patch("repository.services.vector_store_repository_service.RagEmbeddings"):
        with patch("repository.services.vector_store_repository_service.get_vector_store_client", return_value=mock_vs):
            result = service.retrieve_documents("test query", "test-collection", 3, include_score=True)

    assert len(result) == 1
    assert result[0]["page_content"] == "Test content"
    assert result[0]["metadata"]["source"] == "test.txt"
    assert result[0]["metadata"]["similarity_score"] == 0.9  # Direct similarity score
