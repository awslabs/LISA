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


import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials and environment
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
os.environ["AWS_REGION"] = "us-east-1"
os.environ["REGISTERED_REPOSITORIES_PS_PREFIX"] = "/lisa/repositories/"


def test_vector_store_unsupported_type():
    """Test get_vector_store_client raises ValueError for unsupported store type."""
    if "utilities.vector_store" in sys.modules:
        del sys.modules["utilities.vector_store"]

    mock_embeddings = MagicMock()

    with patch("utilities.vector_store.ssm_client") as mock_ssm_client:
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {"Value": json.dumps({"type": "unsupported-store", "endpoint": "test-endpoint"})}
        }

        from utilities.vector_store import get_vector_store_client

        with pytest.raises(ValueError, match="Unrecognized RAG store"):
            get_vector_store_client("test-repo", "test-index", mock_embeddings)


def test_vector_store_opensearch_basic():
    """Test get_vector_store_client with OpenSearch configuration."""
    if "utilities.vector_store" in sys.modules:
        del sys.modules["utilities.vector_store"]

    mock_embeddings = MagicMock()

    with patch("utilities.vector_store.ssm_client") as mock_ssm_client, patch(
        "utilities.vector_store.session"
    ) as mock_session, patch("utilities.vector_store.OpenSearchVectorSearch") as mock_opensearch:

        # Mock SSM client
        mock_ssm_client.get_parameter.return_value = {
            "Parameter": {
                "Value": json.dumps({"type": "opensearch", "endpoint": "search-test.us-east-1.es.amazonaws.com"})
            }
        }

        # Mock session
        mock_credentials = MagicMock()
        mock_credentials.access_key = "test-key"
        mock_credentials.secret_key = "test-secret"
        mock_credentials.token = "test-token"
        mock_session.get_credentials.return_value = mock_credentials
        mock_session.region_name = "us-east-1"

        from utilities.vector_store import get_vector_store_client

        get_vector_store_client("test-repo", "test-index", mock_embeddings)

        # Verify OpenSearchVectorSearch was called
        mock_opensearch.assert_called_once()


def test_vector_store_pgvector_basic():
    """Test get_vector_store_client with PGVector configuration."""
    if "utilities.vector_store" in sys.modules:
        del sys.modules["utilities.vector_store"]

    mock_embeddings = MagicMock()

    with patch("utilities.vector_store.ssm_client") as mock_ssm, patch(
        "utilities.vector_store.PGVector"
    ) as mock_pgvector, patch("utilities.vector_store.get_lambda_role_name") as mock_get_role, patch(
        "utilities.vector_store.generate_auth_token"
    ) as mock_generate_token:

        # Mock SSM fallback since new repo system will fail
        mock_ssm.get_parameter.return_value = {
            "Parameter": {
                "Value": json.dumps({"type": "pgvector", "dbHost": "localhost", "dbPort": 5432, "dbName": "testdb"})
            }
        }

        # Mock IAM auth
        mock_get_role.return_value = "test-role"
        mock_generate_token.return_value = "test-token"

        from utilities.vector_store import get_vector_store_client

        get_vector_store_client("test-repo", "test-index", mock_embeddings)

        # Verify PGVector was called
        mock_pgvector.assert_called_once()
