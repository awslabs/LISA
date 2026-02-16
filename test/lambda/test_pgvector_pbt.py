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

"""Property-based tests for PGVector repository service.

Uses hypothesis to verify universal properties across generated inputs.
"""

import json
import os
from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# Set required environment variables BEFORE any imports
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("RAG_DOCUMENT_TABLE", "test-doc-table")
os.environ.setdefault("RAG_SUB_DOCUMENT_TABLE", "test-subdoc-table")
os.environ.setdefault("REGISTERED_REPOSITORIES_PS_PREFIX", "/test/repos/")

from repository.services.pgvector_repository_service import PGVectorRepositoryService


# --- Strategies ---

# Generate non-empty text strings suitable for connection info fields
_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=50,
).filter(lambda s: len(s.strip()) > 0)

_port_strategy = st.integers(min_value=1, max_value=65535)


@st.composite
def password_auth_connection_info(draw):
    """Generate random connection info dicts that use password authentication.

    Always includes a `passwordSecretId` field to trigger the password auth path.
    """
    return {
        "dbHost": draw(_safe_text),
        "dbPort": str(draw(_port_strategy)),
        "dbName": draw(_safe_text),
        "username": draw(_safe_text),
        "passwordSecretId": draw(_safe_text),
        "type": "pgvector",
    }


_password_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="!@#$%^&*-_=+"),
    min_size=1,
    max_size=100,
)


class TestPasswordAuthCredentialFlow:
    """Property 1: Password auth credential flow.

    **Validates: Requirements 2.1, 2.2**

    For any connection info dictionary containing a `passwordSecretId` field,
    when `_get_vector_store_client` is called, the PGVectorRepositoryService
    shall retrieve the password from Secrets Manager using that secret ID and
    pass the correct username and password to PGEngine.from_connection_string.
    """

    @given(
        conn_info=password_auth_connection_info(),
        password=_password_strategy,
    )
    @settings(max_examples=100)
    def test_password_auth_uses_correct_credentials(self, conn_info, password):
        """**Validates: Requirements 2.1, 2.2**

        For any generated connection info with passwordSecretId, verify that:
        - The password is retrieved from Secrets Manager using the passwordSecretId
        - The correct username and password are embedded in the connection string
          passed to PGEngine.from_connection_string
        """
        repo_config = {
            "repositoryId": "test-repo",
            "type": "pgvector",
            "name": "Test Repo",
            "dbHost": "localhost",
            "embeddingModelId": "test-model",
            "allowedGroups": ["admin"],
            "createdBy": "test-user",
        }
        service = PGVectorRepositoryService(repo_config)

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": json.dumps(conn_info)}
        }
        mock_ssm.exceptions.ParameterNotFound = Exception

        mock_secrets = MagicMock()
        mock_secrets.get_secret_value.return_value = {
            "SecretString": json.dumps({"password": password})
        }

        mock_engine = MagicMock()
        mock_vector_store = MagicMock()

        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1] * 384

        with patch("repository.services.pgvector_repository_service.ssm_client", mock_ssm), \
             patch("repository.services.pgvector_repository_service.secretsmanager_client", mock_secrets), \
             patch("repository.services.pgvector_repository_service.PGEngine") as mock_pg_engine_cls, \
             patch("repository.services.pgvector_repository_service.PGVectorStore") as mock_pg_store_cls:

            mock_pg_engine_cls.from_connection_string.return_value = mock_engine
            mock_pg_store_cls.create_sync.return_value = mock_vector_store

            service._get_vector_store_client("test-collection", mock_embeddings)

            # Verify Secrets Manager was called with the correct secret ID
            mock_secrets.get_secret_value.assert_called_once_with(
                SecretId=conn_info["passwordSecretId"]
            )

            # Verify PGEngine.from_connection_string was called
            mock_pg_engine_cls.from_connection_string.assert_called_once()
            call_kwargs = mock_pg_engine_cls.from_connection_string.call_args

            # Extract the connection string passed to from_connection_string
            connection_url = call_kwargs.kwargs.get("url") or call_kwargs.args[0] if call_kwargs.args else None
            if connection_url is None and "url" in (call_kwargs.kwargs or {}):
                connection_url = call_kwargs.kwargs["url"]

            expected_user = conn_info["username"]
            expected_host = conn_info["dbHost"]
            expected_port = conn_info["dbPort"]
            expected_db = conn_info["dbName"]

            # Verify the connection string contains the correct credentials
            assert f"{expected_user}:{password}@" in connection_url, (
                f"Expected username:password in connection string. "
                f"Got: {connection_url}"
            )
            assert f"@{expected_host}:{expected_port}/{expected_db}" in connection_url, (
                f"Expected host:port/database in connection string. "
                f"Got: {connection_url}"
            )

            # Verify no SSL in connection string for password auth
            assert "sslmode" not in connection_url, (
                f"Password auth should not include SSL. Got: {connection_url}"
            )


# --- IAM Auth Strategies ---

@st.composite
def iam_auth_connection_info(draw):
    """Generate random connection info dicts that use IAM authentication.

    Never includes a `passwordSecretId` field to trigger the IAM auth path.
    """
    return {
        "dbHost": draw(_safe_text),
        "dbPort": str(draw(_port_strategy)),
        "dbName": draw(_safe_text),
        "type": "pgvector",
    }


_role_name_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_"),
    min_size=1,
    max_size=64,
).filter(lambda s: len(s.strip()) > 0)

_auth_token_strategy = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters="-_=+/"),
    min_size=10,
    max_size=200,
).filter(lambda s: len(s.strip()) > 0)


class TestIAMAuthCredentialFlow:
    """Property 2: IAM auth credential flow.

    **Validates: Requirements 3.1, 3.2, 3.3**

    For any connection info dictionary that does not contain a `passwordSecretId` field,
    when `_get_vector_store_client` is called, the PGVectorRepositoryService shall use
    the Lambda execution role name as the database username and generate a fresh RDS IAM
    auth token as the password, passing both to PGEngine.from_connection_string with SSL required.
    """

    @given(
        conn_info=iam_auth_connection_info(),
        role_name=_role_name_strategy,
        auth_token=_auth_token_strategy,
    )
    @settings(max_examples=100)
    def test_iam_auth_uses_role_name_and_token(self, conn_info, role_name, auth_token):
        """**Validates: Requirements 3.1, 3.2, 3.3**

        For any generated connection info without passwordSecretId, verify that:
        - The Lambda role name is used as the database username
        - generate_auth_token is called with the correct host, port, and username
        - SSL is required (sslmode=require in connection string)
        """
        repo_config = {
            "repositoryId": "test-repo",
            "type": "pgvector",
            "name": "Test Repo",
            "dbHost": "localhost",
            "embeddingModelId": "test-model",
            "allowedGroups": ["admin"],
            "createdBy": "test-user",
        }
        service = PGVectorRepositoryService(repo_config)

        mock_ssm = MagicMock()
        mock_ssm.get_parameter.return_value = {
            "Parameter": {"Value": json.dumps(conn_info)}
        }
        mock_ssm.exceptions.ParameterNotFound = Exception

        mock_engine = MagicMock()
        mock_vector_store = MagicMock()

        mock_embeddings = MagicMock()
        mock_embeddings.embed_query.return_value = [0.1] * 384

        with patch("repository.services.pgvector_repository_service.ssm_client", mock_ssm), \
             patch("repository.services.pgvector_repository_service.get_lambda_role_name", return_value=role_name), \
             patch("repository.services.pgvector_repository_service.generate_auth_token", return_value=auth_token) as mock_gen_token, \
             patch("repository.services.pgvector_repository_service.PGEngine") as mock_pg_engine_cls, \
             patch("repository.services.pgvector_repository_service.PGVectorStore") as mock_pg_store_cls:

            mock_pg_engine_cls.from_connection_string.return_value = mock_engine
            mock_pg_store_cls.create_sync.return_value = mock_vector_store

            service._get_vector_store_client("test-collection", mock_embeddings)

            # Verify generate_auth_token was called with correct host, port, and role name
            mock_gen_token.assert_called_once_with(
                conn_info["dbHost"],
                conn_info["dbPort"],
                role_name,
            )

            # Verify PGEngine.from_connection_string was called
            mock_pg_engine_cls.from_connection_string.assert_called_once()
            call_kwargs = mock_pg_engine_cls.from_connection_string.call_args

            # Extract the connection string
            connection_url = call_kwargs.kwargs.get("url") or call_kwargs.args[0] if call_kwargs.args else None
            if connection_url is None and "url" in (call_kwargs.kwargs or {}):
                connection_url = call_kwargs.kwargs["url"]

            expected_host = conn_info["dbHost"]
            expected_port = conn_info["dbPort"]
            expected_db = conn_info["dbName"]

            # Verify the Lambda role name is used as the username
            assert f"{role_name}:{auth_token}@" in connection_url, (
                f"Expected role_name:auth_token in connection string. "
                f"Got: {connection_url}"
            )

            # Verify host, port, and database are correct
            assert f"@{expected_host}:{expected_port}/{expected_db}" in connection_url, (
                f"Expected host:port/database in connection string. "
                f"Got: {connection_url}"
            )

            # Verify SSL is required for IAM auth (Requirement 3.3)
            assert "sslmode=require" in connection_url, (
                f"IAM auth must include sslmode=require. Got: {connection_url}"
            )


class TestScoreNormalizationOutputRange:
    """Property 3: Score normalization output is always in [0, 1].

    **Validates: Requirements 5.1, 5.4**

    For any float input to `_normalize_similarity_score`, the output shall always
    be in the range [0.0, 1.0]. Inputs in [0, 2] map linearly to [1.0, 0.0],
    and inputs outside this range are clamped.
    """

    def _create_service(self):
        """Create a PGVectorRepositoryService instance for testing."""
        repo_config = {
            "repositoryId": "test-repo",
            "type": "pgvector",
            "name": "Test Repo",
            "dbHost": "localhost",
            "embeddingModelId": "test-model",
            "allowedGroups": ["admin"],
            "createdBy": "test-user",
        }
        return PGVectorRepositoryService(repo_config)

    @given(score=st.floats(allow_nan=False, allow_infinity=False))
    @settings(max_examples=100)
    def test_output_always_in_unit_interval(self, score):
        """**Validates: Requirements 5.1, 5.4**

        For any finite float input, the normalized score is always in [0.0, 1.0].
        """
        service = self._create_service()
        result = service._normalize_similarity_score(score)
        assert 0.0 <= result <= 1.0, (
            f"Expected output in [0.0, 1.0] for input {score}, got {result}"
        )
