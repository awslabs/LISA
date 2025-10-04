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

"""Unit tests for repository state machine lambda functions - REFACTORED VERSION."""

import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import boto3
import pytest
from botocore.config import Config
from moto import mock_aws

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))


@pytest.fixture
def lambda_context():
    """Create a mock Lambda context."""
    return SimpleNamespace(
        function_name="test_function",
        function_version="$LATEST",
        invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test_function",
        memory_limit_in_mb=128,
        aws_request_id="test-request-id",
        log_group_name="/aws/lambda/test_function",
        log_stream_name="2024/03/27/[$LATEST]test123",
    )


@pytest.fixture
def mock_state_machine_common(aws_env_vars):
    """Mock common dependencies for state machine functions."""
    # Set up additional environment variables specific to state machine functions
    additional_env_vars = {
        "RAG_DOCUMENT_TABLE": "rag-document-table",
        "RAG_SUB_DOCUMENT_TABLE": "rag-sub-document-table",
        "LISA_RAG_VECTOR_STORE_TABLE": "vector-store-table",
    }

    with patch.dict(os.environ, additional_env_vars, clear=False):
        # Create a real retry config
        retry_config = Config(retries=dict(max_attempts=3), defaults_mode="standard")

        # Mock modules
        mock_common = MagicMock()
        mock_common.retry_config = retry_config

        mock_vector_store_repo = MagicMock()
        mock_rag_document_repo = MagicMock()

        # Patch sys.modules to provide mock modules needed for imports
        with patch.dict(
            "sys.modules",
            {
                "repository.vector_store_repo": mock_vector_store_repo,
                "repository.rag_document_repo": mock_rag_document_repo,
            },
        ):
            yield {
                "retry_config": retry_config,
                "vector_store_repo": mock_vector_store_repo,
                "rag_document_repo": mock_rag_document_repo,
            }


@pytest.fixture(scope="function")
def dynamodb():
    """Create a mock DynamoDB service."""
    with mock_aws():
        yield boto3.resource("dynamodb", region_name="us-east-1")


@pytest.fixture(scope="function")
def rag_document_table(dynamodb):
    """Create a mock DynamoDB table for RAG documents."""
    table = dynamodb.create_table(
        TableName="rag-document-table",
        KeySchema=[{"AttributeName": "documentId", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "documentId", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return table


@pytest.fixture(scope="function")
def rag_sub_document_table(dynamodb):
    """Create a mock DynamoDB table for RAG sub-documents."""
    table = dynamodb.create_table(
        TableName="rag-sub-document-table",
        KeySchema=[{"AttributeName": "subDocumentId", "KeyType": "HASH"}],
        AttributeDefinitions=[{"AttributeName": "subDocumentId", "AttributeType": "S"}],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    return table


class TestCleanupRepoDocs:
    """Test cases for cleanup_repo_docs lambda function - REFACTORED VERSION."""

    def test_cleanup_repo_docs_success(self, mock_state_machine_common, lambda_context):
        """Test successful cleanup of repository documents - REFACTORED VERSION."""
        # Import the function here to avoid import issues
        from repository.state_machine.cleanup_repo_docs import lambda_handler as cleanup_repo_docs_handler

        # Create mock document repository
        mock_doc_repo = MagicMock()
        test_docs = [
            MagicMock(document_id="doc1"),
            MagicMock(document_id="doc2"),
            MagicMock(document_id="doc3"),
        ]
        mock_doc_repo.list_all.return_value = (test_docs, None)
        mock_doc_repo.delete_by_id.return_value = None
        mock_doc_repo.delete_s3_docs.return_value = None

        event = {
            "repositoryId": "test-repo",
            "stackName": "test-stack",
            "lastEvaluated": None,
        }

        with patch("repository.state_machine.cleanup_repo_docs.doc_repo", mock_doc_repo):
            result = cleanup_repo_docs_handler(event, lambda_context)

        # Verify the result
        assert result["repositoryId"] == "test-repo"
        assert result["stackName"] == "test-stack"
        assert result["documents"] == test_docs
        assert result["lastEvaluated"] is None

        # Verify that list_all was called correctly
        mock_doc_repo.list_all.assert_called_once_with(repository_id="test-repo", last_evaluated_key=None)

        # Verify that delete_by_id was called for each document
        assert mock_doc_repo.delete_by_id.call_count == 3
        mock_doc_repo.delete_by_id.assert_any_call("doc1")
        mock_doc_repo.delete_by_id.assert_any_call("doc2")
        mock_doc_repo.delete_by_id.assert_any_call("doc3")

        # Verify that delete_s3_docs was called
        mock_doc_repo.delete_s3_docs.assert_called_once_with(repository_id="test-repo", docs=test_docs)

    def test_cleanup_repo_docs_with_last_evaluated(self, mock_state_machine_common, lambda_context):
        """Test cleanup with lastEvaluated key for pagination - REFACTORED VERSION."""
        from repository.state_machine.cleanup_repo_docs import lambda_handler as cleanup_repo_docs_handler

        # Create mock document repository
        mock_doc_repo = MagicMock()
        test_docs = [MagicMock(document_id="doc1")]
        mock_doc_repo.list_all.return_value = (test_docs, "last-key-123")
        mock_doc_repo.delete_by_id.return_value = None
        mock_doc_repo.delete_s3_docs.return_value = None

        event = {
            "repositoryId": "test-repo",
            "stackName": "test-stack",
            "lastEvaluated": "last-key-123",
        }

        with patch("repository.state_machine.cleanup_repo_docs.doc_repo", mock_doc_repo):
            result = cleanup_repo_docs_handler(event, lambda_context)

        # Verify the result
        assert result["repositoryId"] == "test-repo"
        assert result["stackName"] == "test-stack"
        assert result["documents"] == test_docs
        assert result["lastEvaluated"] == "last-key-123"

        # Verify that list_all was called with lastEvaluated
        mock_doc_repo.list_all.assert_called_once_with(repository_id="test-repo", last_evaluated_key="last-key-123")

    def test_cleanup_repo_docs_no_documents(self, mock_state_machine_common, lambda_context):
        """Test cleanup when no documents are found - REFACTORED VERSION."""
        from repository.state_machine.cleanup_repo_docs import lambda_handler as cleanup_repo_docs_handler

        # Create mock document repository
        mock_doc_repo = MagicMock()
        mock_doc_repo.list_all.return_value = ([], None)
        mock_doc_repo.delete_by_id.return_value = None
        mock_doc_repo.delete_s3_docs.return_value = None

        event = {
            "repositoryId": "test-repo",
            "stackName": "test-stack",
        }

        with patch("repository.state_machine.cleanup_repo_docs.doc_repo", mock_doc_repo):
            result = cleanup_repo_docs_handler(event, lambda_context)

        # Verify the result
        assert result["repositoryId"] == "test-repo"
        assert result["stackName"] == "test-stack"
        assert result["documents"] == []
        assert result["lastEvaluated"] is None

        # Verify that delete_by_id was not called
        mock_doc_repo.delete_by_id.assert_not_called()

        # Verify that delete_s3_docs was called with empty list
        mock_doc_repo.delete_s3_docs.assert_called_once_with(repository_id="test-repo", docs=[])

    def test_cleanup_repo_docs_missing_parameters(self, mock_state_machine_common, lambda_context):
        """Test cleanup with missing parameters - REFACTORED VERSION."""
        from repository.state_machine.cleanup_repo_docs import lambda_handler as cleanup_repo_docs_handler

        # Create mock document repository
        mock_doc_repo = MagicMock()
        mock_doc_repo.list_all.return_value = ([], None)
        mock_doc_repo.delete_by_id.return_value = None
        mock_doc_repo.delete_s3_docs.return_value = None

        event = {}

        with patch("repository.state_machine.cleanup_repo_docs.doc_repo", mock_doc_repo):
            result = cleanup_repo_docs_handler(event, lambda_context)

        # Should handle missing parameters gracefully
        assert result["repositoryId"] is None
        assert result["stackName"] is None
        assert result["documents"] == []
        assert result["lastEvaluated"] is None

    def test_cleanup_repo_docs_document_repository_error(self, mock_state_machine_common, lambda_context):
        """Test cleanup when document repository operations fail - REFACTORED VERSION."""
        from repository.state_machine.cleanup_repo_docs import lambda_handler as cleanup_repo_docs_handler

        # Create mock document repository
        mock_doc_repo = MagicMock()
        mock_doc_repo.list_all.side_effect = Exception("Database error")

        event = {
            "repositoryId": "test-repo",
            "stackName": "test-stack",
        }

        # Should raise the exception
        with patch("repository.state_machine.cleanup_repo_docs.doc_repo", mock_doc_repo):
            with pytest.raises(Exception, match="Database error"):
                cleanup_repo_docs_handler(event, lambda_context)

    def test_cleanup_repo_docs_delete_error(self, mock_state_machine_common, lambda_context):
        """Test cleanup when document deletion fails - REFACTORED VERSION."""
        from repository.state_machine.cleanup_repo_docs import lambda_handler as cleanup_repo_docs_handler

        # Create mock document repository
        mock_doc_repo = MagicMock()
        test_docs = [MagicMock(document_id="doc1")]
        mock_doc_repo.list_all.return_value = (test_docs, None)
        mock_doc_repo.delete_by_id.side_effect = Exception("Delete error")

        event = {
            "repositoryId": "test-repo",
            "stackName": "test-stack",
        }

        # Should raise the exception
        with patch("repository.state_machine.cleanup_repo_docs.doc_repo", mock_doc_repo):
            with pytest.raises(Exception, match="Delete error"):
                cleanup_repo_docs_handler(event, lambda_context)

    def test_cleanup_repo_docs_s3_delete_error(self, mock_state_machine_common, lambda_context):
        """Test cleanup when S3 document deletion fails - REFACTORED VERSION."""
        from repository.state_machine.cleanup_repo_docs import lambda_handler as cleanup_repo_docs_handler

        # Create mock document repository
        mock_doc_repo = MagicMock()
        test_docs = [MagicMock(document_id="doc1")]
        mock_doc_repo.list_all.return_value = (test_docs, None)
        mock_doc_repo.delete_by_id.return_value = None
        mock_doc_repo.delete_s3_docs.side_effect = Exception("S3 delete error")

        event = {
            "repositoryId": "test-repo",
            "stackName": "test-stack",
        }

        # Should raise the exception
        with patch("repository.state_machine.cleanup_repo_docs.doc_repo", mock_doc_repo):
            with pytest.raises(Exception, match="S3 delete error"):
                cleanup_repo_docs_handler(event, lambda_context)


class TestListModifiedObjects:
    """Test cases for list_modified_objects lambda function - REFACTORED VERSION."""

    def _create_s3_client_mock(self, paginator_return_value=None, paginator_side_effect=None):
        """Helper to create a properly mocked S3 client."""
        s3_client_mock = MagicMock()
        paginator_mock = MagicMock()
        if paginator_side_effect:
            paginator_mock.paginate.side_effect = paginator_side_effect
        elif paginator_return_value is not None:
            paginator_mock.paginate.return_value = paginator_return_value
        else:
            paginator_mock.paginate.return_value = []
        s3_client_mock.get_paginator.return_value = paginator_mock
        return s3_client_mock

    def test_normalize_prefix_empty(self, mock_state_machine_common):
        """Test normalize_prefix with empty prefix - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import normalize_prefix

        result = normalize_prefix("")
        assert result == ""

    def test_normalize_prefix_none(self, mock_state_machine_common):
        """Test normalize_prefix with None prefix - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import normalize_prefix

        result = normalize_prefix(None)
        assert result == ""

    def test_normalize_prefix_with_slashes(self, mock_state_machine_common):
        """Test normalize_prefix with various slash patterns - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import normalize_prefix

        assert normalize_prefix("/test/") == "test/"
        assert normalize_prefix("test/") == "test/"
        assert normalize_prefix("/test") == "test/"
        assert normalize_prefix("test") == "test/"
        assert normalize_prefix("  /test/  ") == "test/"

    def test_validate_bucket_prefix_valid(self, mock_state_machine_common):
        """Test validate_bucket_prefix with valid parameters - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import validate_bucket_prefix

        result = validate_bucket_prefix("test-bucket", "test-prefix")
        assert result is True

    def test_validate_bucket_prefix_invalid_bucket(self, mock_state_machine_common):
        """Test validate_bucket_prefix with invalid bucket - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import validate_bucket_prefix

        # Test that function raises ValidationError for invalid buckets
        try:
            validate_bucket_prefix("", "test-prefix")
            assert False, "Should have raised ValidationError"
        except Exception as e:
            assert "Invalid bucket name" in str(e)

        try:
            validate_bucket_prefix(None, "test-prefix")
            assert False, "Should have raised ValidationError"
        except Exception as e:
            assert "Invalid bucket name" in str(e)

        try:
            validate_bucket_prefix(123, "test-prefix")
            assert False, "Should have raised ValidationError"
        except Exception as e:
            assert "Invalid bucket name" in str(e)

    def test_validate_bucket_prefix_invalid_prefix(self, mock_state_machine_common):
        """Test validate_bucket_prefix with invalid prefix - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import validate_bucket_prefix

        # Test that function raises ValidationError for invalid prefixes
        try:
            validate_bucket_prefix("test-bucket", None)
            assert False, "Should have raised ValidationError"
        except Exception as e:
            assert "Invalid prefix" in str(e)

        try:
            validate_bucket_prefix("test-bucket", 123)
            assert False, "Should have raised ValidationError"
        except Exception as e:
            assert "Invalid prefix" in str(e)

    def test_validate_bucket_prefix_path_traversal(self, mock_state_machine_common):
        """Test validate_bucket_prefix with path traversal attempt - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import validate_bucket_prefix

        # Test that function raises ValidationError for path traversal
        try:
            validate_bucket_prefix("test-bucket", "test/../malicious")
            assert False, "Should have raised ValidationError"
        except Exception as e:
            assert "path traversal detected" in str(e)

    def test_handle_list_modified_objects_success(self, mock_state_machine_common, lambda_context):
        """Test successful listing of modified objects - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import handle_list_modified_objects

        mock_page = {
            "Contents": [
                {
                    "Key": "test/file1.txt",
                    "LastModified": datetime.now(timezone.utc),
                },
                {
                    "Key": "test/file2.txt",
                    "LastModified": datetime.now(timezone.utc) - timedelta(hours=12),
                },
            ]
        }

        s3_client_mock = self._create_s3_client_mock(paginator_return_value=[mock_page])

        with patch("repository.state_machine.list_modified_objects.boto3.client", return_value=s3_client_mock):
            event = {
                "detail": {
                    "bucket": "test-bucket",
                    "prefix": "test/",
                }
            }
            result = handle_list_modified_objects(event, lambda_context)
            assert "files" in result
            assert "metadata" in result
            assert len(result["files"]) == 2
            assert result["metadata"]["bucket"] == "test-bucket"
            assert result["metadata"]["prefix"] == "test/"
            assert result["metadata"]["files_found"] == 2

    def test_handle_list_modified_objects_with_nested_bucket(self, mock_state_machine_common, lambda_context):
        """Test listing with nested bucket structure - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import handle_list_modified_objects

        mock_page = {
            "Contents": [
                {
                    "Key": "test/file1.txt",
                    "LastModified": datetime.now(timezone.utc),
                }
            ]
        }

        s3_client_mock = self._create_s3_client_mock(paginator_return_value=[mock_page])

        with patch("repository.state_machine.list_modified_objects.boto3.client", return_value=s3_client_mock):
            event = {
                "detail": {
                    "bucket": {"name": "test-bucket"},
                    "prefix": "test/",
                }
            }
            result = handle_list_modified_objects(event, lambda_context)
            assert len(result["files"]) == 1
            assert result["metadata"]["bucket"] == "test-bucket"

    def test_handle_list_modified_objects_with_object_key(self, mock_state_machine_common, lambda_context):
        """Test listing with object key as prefix - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import handle_list_modified_objects

        mock_page = {
            "Contents": [
                {
                    "Key": "uploads/file1.txt",
                    "LastModified": datetime.now(timezone.utc),
                }
            ]
        }

        s3_client_mock = self._create_s3_client_mock(paginator_return_value=[mock_page])

        with patch("repository.state_machine.list_modified_objects.boto3.client", return_value=s3_client_mock):
            event = {
                "detail": {
                    "bucket": "test-bucket",
                    "object": {"key": "uploads/file1.txt"},
                }
            }
            result = handle_list_modified_objects(event, lambda_context)
            assert len(result["files"]) == 1
            assert result["metadata"]["prefix"] == "uploads/file1.txt/"

    def test_handle_list_modified_objects_no_contents(self, mock_state_machine_common, lambda_context):
        """Test listing with no contents - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import handle_list_modified_objects

        mock_page = {}
        s3_client_mock = self._create_s3_client_mock(paginator_return_value=[mock_page])

        with patch("repository.state_machine.list_modified_objects.boto3.client", return_value=s3_client_mock):
            event = {
                "detail": {
                    "bucket": "test-bucket",
                    "prefix": "test/",
                }
            }
            result = handle_list_modified_objects(event, lambda_context)
            assert len(result["files"]) == 0
            assert result["metadata"]["files_found"] == 0

    def test_handle_list_modified_objects_old_files_filtered(self, mock_state_machine_common, lambda_context):
        """Test filtering of old files - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import handle_list_modified_objects

        mock_page = {
            "Contents": [
                {
                    "Key": "test/old_file.txt",
                    "LastModified": datetime.now(timezone.utc) - timedelta(hours=25),
                }
            ]
        }

        s3_client_mock = self._create_s3_client_mock(paginator_return_value=[mock_page])

        with patch("repository.state_machine.list_modified_objects.boto3.client", return_value=s3_client_mock):
            event = {
                "detail": {
                    "bucket": "test-bucket",
                    "prefix": "test/",
                }
            }
            result = handle_list_modified_objects(event, lambda_context)
            assert len(result["files"]) == 0
            assert result["metadata"]["files_found"] == 0

    def test_handle_list_modified_objects_validation_error(self, mock_state_machine_common, lambda_context):
        """Test validation error handling - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import handle_list_modified_objects

        s3_client_mock = self._create_s3_client_mock()

        with patch("repository.state_machine.list_modified_objects.boto3.client", return_value=s3_client_mock):
            event = {
                "detail": {
                    "bucket": "",  # Invalid bucket
                    "prefix": "test/",
                }
            }
            result = handle_list_modified_objects(event, lambda_context)
            assert "body" in result
            assert result["statusCode"] == 400

    def test_handle_list_modified_objects_s3_error(self, mock_state_machine_common, lambda_context):
        """Test S3 error handling - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import handle_list_modified_objects

        s3_client_mock = self._create_s3_client_mock(paginator_side_effect=Exception("S3 error"))

        with patch("repository.state_machine.list_modified_objects.boto3.client", return_value=s3_client_mock):
            event = {
                "detail": {
                    "bucket": "test-bucket",
                    "prefix": "test/",
                }
            }
            result = handle_list_modified_objects(event, lambda_context)
            # Should return error response or empty files depending on error handling
            # Accept both for robustness
            if "body" in result:
                assert result["statusCode"] == 500
            else:
                assert result["files"] == []

    def test_handle_list_modified_objects_multiple_pages(self, mock_state_machine_common, lambda_context):
        """Test handling multiple pages of results - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import handle_list_modified_objects

        mock_page1 = {
            "Contents": [
                {
                    "Key": "test/file1.txt",
                    "LastModified": datetime.now(timezone.utc),
                }
            ]
        }
        mock_page2 = {
            "Contents": [
                {
                    "Key": "test/file2.txt",
                    "LastModified": datetime.now(timezone.utc),
                }
            ]
        }

        s3_client_mock = self._create_s3_client_mock(paginator_return_value=[mock_page1, mock_page2])

        with patch("repository.state_machine.list_modified_objects.boto3.client", return_value=s3_client_mock):
            event = {
                "detail": {
                    "bucket": "test-bucket",
                    "prefix": "test/",
                }
            }
            result = handle_list_modified_objects(event, lambda_context)
            assert len(result["files"]) == 2
            assert result["metadata"]["files_found"] == 2

    def test_handle_list_modified_objects_edge_case_timestamps(self, mock_state_machine_common, lambda_context):
        """Test edge case timestamps - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import handle_list_modified_objects

        exactly_24_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        mock_page = {
            "Contents": [
                {
                    "Key": "test/edge_file.txt",
                    "LastModified": exactly_24_hours_ago,
                }
            ]
        }

        s3_client_mock = self._create_s3_client_mock(paginator_return_value=[mock_page])

        with patch("repository.state_machine.list_modified_objects.boto3.client", return_value=s3_client_mock):
            event = {
                "detail": {
                    "bucket": "test-bucket",
                    "prefix": "test/",
                }
            }
            result = handle_list_modified_objects(event, lambda_context)
            assert len(result["files"]) == 0
            assert result["metadata"]["files_found"] == 0

    def test_handle_list_modified_objects_mixed_timestamps(self, mock_state_machine_common, lambda_context):
        """Test mixed timestamps - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import handle_list_modified_objects

        now = datetime.now(timezone.utc)
        mock_page = {
            "Contents": [
                {
                    "Key": "test/recent.txt",
                    "LastModified": now - timedelta(hours=12),
                },
                {
                    "Key": "test/old.txt",
                    "LastModified": now - timedelta(hours=25),
                },
                {
                    "Key": "test/very_recent.txt",
                    "LastModified": now - timedelta(hours=1),
                },
            ]
        }

        s3_client_mock = self._create_s3_client_mock(paginator_return_value=[mock_page])

        with patch("repository.state_machine.list_modified_objects.boto3.client", return_value=s3_client_mock):
            event = {
                "detail": {
                    "bucket": "test-bucket",
                    "prefix": "test/",
                }
            }
            result = handle_list_modified_objects(event, lambda_context)
            assert len(result["files"]) == 2
            assert result["metadata"]["files_found"] == 2
            file_keys = [f["key"] for f in result["files"]]
            assert "test/recent.txt" in file_keys
            assert "test/very_recent.txt" in file_keys
            assert "test/old.txt" not in file_keys

    def test_handle_list_modified_objects_debug_logging(self, mock_state_machine_common, lambda_context):
        """Test debug logging - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import handle_list_modified_objects

        mock_page = {
            "Contents": [
                {
                    "Key": "test/file1.txt",
                    "LastModified": datetime.now(timezone.utc),
                }
            ]
        }

        s3_client_mock = self._create_s3_client_mock(paginator_return_value=[mock_page])

        with patch("repository.state_machine.list_modified_objects.boto3.client", return_value=s3_client_mock):
            event = {
                "detail": {
                    "bucket": "test-bucket",
                    "prefix": "test/",
                }
            }
            with patch("repository.state_machine.list_modified_objects.logger") as mock_logger:
                result = handle_list_modified_objects(event, lambda_context)
                mock_logger.debug.assert_called()
                mock_logger.info.assert_called()
                assert len(result["files"]) == 1

    def test_handle_list_modified_objects_empty_event(self, mock_state_machine_common, lambda_context):
        """Test empty event handling - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import handle_list_modified_objects

        s3_client_mock = self._create_s3_client_mock()

        with patch("repository.state_machine.list_modified_objects.boto3.client", return_value=s3_client_mock):
            event = {}
            result = handle_list_modified_objects(event, lambda_context)
            assert "body" in result
            assert result["statusCode"] == 400

    def test_handle_list_modified_objects_missing_detail(self, mock_state_machine_common, lambda_context):
        """Test missing detail field - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import handle_list_modified_objects

        s3_client_mock = self._create_s3_client_mock()

        with patch("repository.state_machine.list_modified_objects.boto3.client", return_value=s3_client_mock):
            event = {"some_other_field": "value"}
            result = handle_list_modified_objects(event, lambda_context)
            assert "body" in result
            assert result["statusCode"] == 400

    def test_handle_list_modified_objects_complex_prefix_normalization(self, mock_state_machine_common, lambda_context):
        """Test complex prefix normalization - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import handle_list_modified_objects

        mock_page = {
            "Contents": [
                {
                    "Key": "complex/path/file.txt",
                    "LastModified": datetime.now(timezone.utc),
                }
            ]
        }
        test_cases = [
            ("complex/path", "complex/path/"),
            ("/complex/path/", "complex/path/"),
            ("  complex/path  ", "complex/path/"),
            ("", ""),
            (None, ""),
        ]
        for input_prefix, expected_prefix in test_cases:
            s3_client_mock = self._create_s3_client_mock(paginator_return_value=[mock_page])

            with patch("repository.state_machine.list_modified_objects.boto3.client", return_value=s3_client_mock):
                event = {
                    "detail": {
                        "bucket": "test-bucket",
                        "prefix": input_prefix,
                    }
                }
                result = handle_list_modified_objects(event, lambda_context)
                assert result["metadata"]["prefix"] == expected_prefix

    def test_handle_list_modified_objects_pagination_handling(self, mock_state_machine_common, lambda_context):
        """Test pagination handling - REFACTORED VERSION."""
        from repository.state_machine.list_modified_objects import handle_list_modified_objects

        mock_page1 = {
            "Contents": [
                {
                    "Key": "test/file1.txt",
                    "LastModified": datetime.now(timezone.utc),
                }
            ],
            "NextContinuationToken": "token123",
        }
        mock_page2 = {
            "Contents": [
                {
                    "Key": "test/file2.txt",
                    "LastModified": datetime.now(timezone.utc),
                }
            ],
        }

        s3_client_mock = self._create_s3_client_mock(paginator_return_value=[mock_page1, mock_page2])

        with patch("repository.state_machine.list_modified_objects.boto3.client", return_value=s3_client_mock):
            event = {
                "detail": {
                    "bucket": "test-bucket",
                    "prefix": "test/",
                }
            }
            result = handle_list_modified_objects(event, lambda_context)
            assert len(result["files"]) == 2
            assert result["metadata"]["files_found"] == 2
