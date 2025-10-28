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

from repository.lambda_functions import _similarity_search, _similarity_search_with_score


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
