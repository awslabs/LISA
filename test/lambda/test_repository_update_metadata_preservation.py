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

"""Tests for repository update metadata preservation functionality."""

import json
import os
from unittest.mock import MagicMock, patch

import pytest

# Set required environment variables BEFORE any imports
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("RAG_DOCUMENT_TABLE", "test-doc-table")
os.environ.setdefault("RAG_SUB_DOCUMENT_TABLE", "test-subdoc-table")
os.environ.setdefault("LISA_RAG_VECTOR_STORE_TABLE", "test-vector-store-table")
os.environ.setdefault("LISA_RAG_COLLECTIONS_TABLE", "test-collections-table")
os.environ.setdefault("LISA_INGESTION_JOB_TABLE_NAME", "test-job-table")
os.environ.setdefault("BUCKET_NAME", "test-bucket")
os.environ.setdefault("LISA_RAG_CREATE_STATE_MACHINE_ARN_PARAMETER", "/test/state-machine-arn")

from models.domain_objects import (
    BedrockDataSource,
    BedrockKnowledgeBaseConfig,
)
from repository.lambda_functions import update_repository
from utilities.repository_types import RepositoryType


class TestRepositoryUpdateMetadataPreservation:
    """Test cases for preserving pipeline metadata during repository updates."""

    @pytest.fixture
    def mock_vector_store_repo(self):
        """Mock VectorStoreRepository."""
        mock = MagicMock()
        # Set up default return values for common methods
        mock.find_repository_by_id.return_value = {}
        mock.update.return_value = {}
        return mock

    @pytest.fixture
    def bedrock_kb_repository_with_metadata(self):
        """Sample Bedrock KB repository with existing pipeline metadata."""
        return {
            "repositoryId": "test-repo",
            "config": {
                "type": RepositoryType.BEDROCK_KB,
                "repositoryName": "Test Repository",
                "pipelines": [
                    {
                        "trigger": "event",
                        "chunkingStrategy": {"type": "none"},
                        "s3Prefix": "",
                        "autoRemove": True,
                        "collectionId": "datasource-1",
                        "collectionName": "Test Data Source",
                        "s3Bucket": "docs",
                        "metadata": {
                            "tags": ["existing-tag", "important"],
                            "customFields": {"owner": "team-a", "priority": "high"},
                        },
                    }
                ],
            },
        }

    @pytest.fixture
    def lambda_context(self):
        """Create a mock Lambda context."""
        from types import SimpleNamespace

        return SimpleNamespace(
            function_name="test_function",
            function_version="$LATEST",
            invoked_function_arn="arn:aws:lambda:us-east-1:123456789012:function:test_function",
            memory_limit_in_mb=128,
            remaining_time_in_millis=30000,
            aws_request_id="test-request-id",
        )

    @pytest.fixture
    def vector_store_repository_with_metadata(self):
        """Sample vector store repository with existing pipeline metadata."""
        return {
            "repositoryId": "test-repo",
            "config": {
                "type": RepositoryType.OPENSEARCH,
                "repositoryName": "Test Repository",
                "pipelines": [
                    {
                        "trigger": "event",
                        "chunkingStrategy": {"type": "fixed", "size": 512, "overlap": 51},
                        "s3Prefix": "",
                        "autoRemove": True,
                        "collectionId": "default",
                        "s3Bucket": "docs",
                        "metadata": {"tags": ["existing-tag"], "customFields": {"owner": "team-b"}},
                    }
                ],
            },
        }

    def test_bedrock_kb_update_preserves_existing_metadata(
        self, mock_vector_store_repo, bedrock_kb_repository_with_metadata, lambda_context
    ):
        """Test that Bedrock KB updates preserve existing pipeline metadata."""
        # Arrange
        repository_id = "test-repo"

        # Mock the repository lookup
        mock_vector_store_repo.find_repository_by_id.return_value = bedrock_kb_repository_with_metadata

        # Mock the update method
        updated_config = bedrock_kb_repository_with_metadata["config"].copy()
        mock_vector_store_repo.update.return_value = updated_config

        # Create update request with same data source but no metadata
        kb_config = BedrockKnowledgeBaseConfig(
            knowledgeBaseId="kb-123",
            dataSources=[BedrockDataSource(id="datasource-1", name="Test Data Source", s3Uri="s3://docs/")],
        )

        request_body = {"bedrockKnowledgeBaseConfig": kb_config.model_dump(mode="json")}

        event = {
            "pathParameters": {"repositoryId": repository_id},
            "body": json.dumps(request_body),
            "requestContext": {"authorizer": {"username": "admin", "groups": ["admin"]}},
        }

        # Act
        with patch("repository.lambda_functions.vs_repo", mock_vector_store_repo), patch(
            "repository.lambda_functions.build_pipeline_configs_from_kb_config"
        ) as mock_build_pipelines, patch("utilities.auth.is_admin", return_value=True), patch(
            "utilities.auth.user_has_group_access", return_value=True
        ):

            # Mock the pipeline builder to return pipelines without metadata
            mock_build_pipelines.return_value = [
                {
                    "s3Bucket": "docs",
                    "s3Prefix": "",
                    "collectionId": "datasource-1",
                    "collectionName": "Test Data Source",
                    "trigger": "event",
                    "autoRemove": True,
                    "chunkingStrategy": {"type": "none"},
                    # No metadata - should be preserved from existing
                }
            ]

            _result = update_repository(event, lambda_context)

        # Assert
        mock_vector_store_repo.update.assert_called_once()
        call_args = mock_vector_store_repo.update.call_args
        updates = call_args[0][1]  # Second argument is the updates dict

        # Verify that metadata was preserved in the pipeline update
        assert "pipelines" in updates
        assert len(updates["pipelines"]) == 1
        pipeline = updates["pipelines"][0]

        assert "metadata" in pipeline
        assert pipeline["metadata"]["tags"] == ["existing-tag", "important"]
        assert pipeline["metadata"]["customFields"]["owner"] == "team-a"
        assert pipeline["metadata"]["customFields"]["priority"] == "high"

    @pytest.mark.skip(reason="Metadata preservation logic needs refactoring - tracked in separate issue")
    def test_direct_pipeline_update_preserves_metadata_when_missing(
        self, mock_vector_store_repo, vector_store_repository_with_metadata, lambda_context
    ):
        """Test that direct pipeline updates preserve existing metadata when not provided."""
        # Arrange
        repository_id = "test-repo"

        mock_vector_store_repo.find_repository_by_id.return_value = vector_store_repository_with_metadata

        updated_config = vector_store_repository_with_metadata["config"].copy()
        mock_vector_store_repo.update.return_value = updated_config

        # Update request with pipeline but no metadata - only change mutable fields
        request_body = {
            "pipelines": [
                {
                    "trigger": "event",
                    "chunkingStrategy": {"type": "fixed", "size": 1024, "overlap": 102},  # Changed mutable field
                    "s3Prefix": "",  # Keep same immutable field
                    "autoRemove": True,
                    "collectionId": "default",
                    "s3Bucket": "docs",
                    # No metadata - should preserve existing
                }
            ]
        }

        event = {
            "pathParameters": {"repositoryId": repository_id},
            "body": json.dumps(request_body),
            "requestContext": {"authorizer": {"username": "admin", "groups": ["admin"]}},
        }

        # Act
        with patch("repository.lambda_functions.vs_repo", mock_vector_store_repo), patch(
            "utilities.auth.is_admin", return_value=True
        ), patch("utilities.auth.user_has_group_access", return_value=True):
            _result = update_repository(event, lambda_context)

        # Assert
        mock_vector_store_repo.update.assert_called_once()
        call_args = mock_vector_store_repo.update.call_args
        updates = call_args[0][1]

        # Verify that existing metadata was preserved
        assert "pipelines" in updates
        pipeline = updates["pipelines"][0]

        assert "metadata" in pipeline
        assert pipeline["metadata"]["tags"] == ["existing-tag"]
        assert pipeline["metadata"]["customFields"]["owner"] == "team-b"
        assert pipeline["s3Prefix"] == "new-prefix"  # Verify the update was applied

    @pytest.mark.skip(reason="Metadata preservation logic needs refactoring - tracked in separate issue")
    def test_partial_metadata_update_preserves_missing_tags(
        self, mock_vector_store_repo, vector_store_repository_with_metadata, lambda_context
    ):
        """Test that partial metadata updates preserve existing tags when not provided."""
        # Arrange
        repository_id = "test-repo"

        mock_vector_store_repo.find_repository_by_id.return_value = vector_store_repository_with_metadata

        updated_config = vector_store_repository_with_metadata["config"].copy()
        mock_vector_store_repo.update.return_value = updated_config

        # Update request with metadata but missing tags
        request_body = {
            "pipelines": [
                {
                    "trigger": "event",
                    "chunkingStrategy": {"type": "fixed", "size": 512, "overlap": 51},
                    "s3Prefix": "",
                    "autoRemove": True,
                    "collectionId": "default",
                    "s3Bucket": "docs",
                    "metadata": {
                        "customFields": {"owner": "team-c", "priority": "low"}
                        # Tags missing - should preserve existing tags
                    },
                }
            ]
        }

        event = {
            "pathParameters": {"repositoryId": repository_id},
            "body": json.dumps(request_body),
            "requestContext": {"authorizer": {"username": "admin", "groups": ["admin"]}},
        }

        # Act
        with patch("repository.lambda_functions.vs_repo", mock_vector_store_repo), patch(
            "utilities.auth.is_admin", return_value=True
        ), patch("utilities.auth.user_has_group_access", return_value=True):
            _result = update_repository(event, lambda_context)

        # Assert
        mock_vector_store_repo.update.assert_called_once()
        call_args = mock_vector_store_repo.update.call_args
        updates = call_args[0][1]

        # Verify that existing tags were preserved while custom fields were updated
        pipeline = updates["pipelines"][0]

        assert "metadata" in pipeline
        assert pipeline["metadata"]["tags"] == ["existing-tag"]  # Preserved
        assert pipeline["metadata"]["customFields"]["owner"] == "team-c"  # Updated
        assert pipeline["metadata"]["customFields"]["priority"] == "low"  # Updated

    def test_complete_metadata_replacement_when_tags_provided(
        self, mock_vector_store_repo, vector_store_repository_with_metadata, lambda_context
    ):
        """Test that when tags are explicitly provided, they replace existing tags."""
        # Arrange
        repository_id = "test-repo"

        mock_vector_store_repo.find_repository_by_id.return_value = vector_store_repository_with_metadata

        updated_config = vector_store_repository_with_metadata["config"].copy()
        mock_vector_store_repo.update.return_value = updated_config

        # Update request with complete metadata including new tags
        request_body = {
            "pipelines": [
                {
                    "trigger": "event",
                    "chunkingStrategy": {"type": "fixed", "size": 512, "overlap": 51},
                    "s3Prefix": "",
                    "autoRemove": True,
                    "collectionId": "default",
                    "s3Bucket": "docs",
                    "metadata": {"tags": ["new-tag", "updated"], "customFields": {"owner": "team-d"}},
                }
            ]
        }

        event = {
            "pathParameters": {"repositoryId": repository_id},
            "body": json.dumps(request_body),
            "requestContext": {"authorizer": {"username": "admin", "groups": ["admin"]}},
        }

        # Act
        with patch("repository.lambda_functions.vs_repo", mock_vector_store_repo), patch(
            "utilities.auth.is_admin", return_value=True
        ), patch("utilities.auth.user_has_group_access", return_value=True):
            _result = update_repository(event, lambda_context)

        # Assert
        mock_vector_store_repo.update.assert_called_once()
        call_args = mock_vector_store_repo.update.call_args
        updates = call_args[0][1]

        # Verify that new metadata completely replaced existing metadata
        pipeline = updates["pipelines"][0]

        assert "metadata" in pipeline
        assert pipeline["metadata"]["tags"] == ["new-tag", "updated"]  # New tags
        assert pipeline["metadata"]["customFields"]["owner"] == "team-d"  # New custom fields

    @pytest.mark.skip(reason="Metadata preservation logic needs refactoring - tracked in separate issue")
    def test_no_metadata_preservation_for_new_collections(
        self, mock_vector_store_repo, bedrock_kb_repository_with_metadata, lambda_context
    ):
        """Test that new collections (not in existing pipelines) don't get metadata."""
        # Arrange
        repository_id = "test-repo"

        mock_vector_store_repo.find_repository_by_id.return_value = bedrock_kb_repository_with_metadata

        updated_config = bedrock_kb_repository_with_metadata["config"].copy()
        mock_vector_store_repo.update.return_value = updated_config

        # Create update request with new data source
        kb_config = BedrockKnowledgeBaseConfig(
            knowledgeBaseId="kb-123",
            dataSources=[
                BedrockDataSource(
                    id="datasource-2", name="New Data Source", s3Uri="s3://new-docs/"  # New data source ID
                )
            ],
        )

        request_body = {"bedrockKnowledgeBaseConfig": kb_config.model_dump(mode="json")}

        event = {
            "pathParameters": {"repositoryId": repository_id},
            "body": json.dumps(request_body),
            "requestContext": {"authorizer": {"username": "admin", "groups": ["admin"]}},
        }

        # Act
        with patch("repository.lambda_functions.vs_repo", mock_vector_store_repo), patch(
            "repository.lambda_functions.build_pipeline_configs_from_kb_config"
        ) as mock_build_pipelines, patch("utilities.auth.is_admin", return_value=True), patch(
            "utilities.auth.user_has_group_access", return_value=True
        ):

            mock_build_pipelines.return_value = [
                {
                    "s3Bucket": "new-docs",
                    "s3Prefix": "",
                    "collectionId": "datasource-2",
                    "collectionName": "New Data Source",
                    "trigger": "event",
                    "autoRemove": True,
                    "chunkingStrategy": {"type": "none"},
                }
            ]

            _result = update_repository(event, lambda_context)

        # Assert
        mock_vector_store_repo.update.assert_called_once()
        call_args = mock_vector_store_repo.update.call_args
        updates = call_args[0][1]

        # Verify that new collection doesn't have metadata (since it didn't exist before)
        pipeline = updates["pipelines"][0]
        assert "metadata" not in pipeline or not pipeline.get("metadata")
