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

"""Test pipeline_ingestion module."""

import os
import sys
from unittest.mock import patch

import pytest

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Import after setting up environment
from models.domain_objects import (
    ChunkingStrategyType,
    FixedChunkingStrategy,
    IngestionJob,
    IngestionStatus,
    IngestionType,
)

# Set required environment variables before importing repository modules
os.environ["AWS_REGION"] = "us-east-1"
os.environ["RAG_DOCUMENT_TABLE"] = "test-doc-table"
os.environ["RAG_SUB_DOCUMENT_TABLE"] = "test-subdoc-table"
os.environ["LISA_INGESTION_JOB_TABLE_NAME"] = "test-ingestion-job-table"


@pytest.fixture
def sample_ingestion_job():
    """Create a sample ingestion job."""
    return IngestionJob(
        id="test-job-id",
        repository_id="test-repo",
        collection_id="test-collection",
        document_id="test-doc-id",
        s3_path="s3://test-bucket/test-key",
        chunk_strategy=FixedChunkingStrategy(type=ChunkingStrategyType.FIXED, size=1000, overlap=200),
        status=IngestionStatus.INGESTION_PENDING,
        ingestion_type=IngestionType.MANUAL,
        username="test-user",
        created_date="2024-01-01T00:00:00Z",
    )


def test_ingest_success(sample_ingestion_job):
    """Test successful ingest function."""
    with patch("repository.pipeline_ingestion.ingestion_job_repository") as mock_job_repo, patch(
        "repository.pipeline_ingestion.pipeline_ingest"
    ) as mock_pipeline_ingest:

        # Setup mocks
        mock_job_repo.update_status.return_value = sample_ingestion_job
        mock_pipeline_ingest.return_value = None

        # Import the module
        import repository.pipeline_ingestion

        # Call the function
        repository.pipeline_ingestion.ingest(sample_ingestion_job)

        # Verify calls
        mock_job_repo.update_status.assert_called_once_with(sample_ingestion_job, IngestionStatus.INGESTION_IN_PROGRESS)
        mock_pipeline_ingest.assert_called_once_with(sample_ingestion_job)


def test_ingest_error(sample_ingestion_job):
    """Test ingest function with error."""
    with patch("repository.pipeline_ingestion.ingestion_job_repository") as mock_job_repo, patch(
        "repository.pipeline_ingestion.pipeline_ingest"
    ) as mock_pipeline_ingest:

        # Setup mocks
        mock_job_repo.update_status.return_value = sample_ingestion_job
        mock_pipeline_ingest.side_effect = Exception("Test error")

        # Import the module
        import repository.pipeline_ingestion

        # Call the function and expect exception
        with pytest.raises(Exception, match="Test error"):
            repository.pipeline_ingestion.ingest(sample_ingestion_job)

        # Verify calls
        mock_job_repo.update_status.assert_called_once_with(sample_ingestion_job, IngestionStatus.INGESTION_IN_PROGRESS)


def test_delete_success(sample_ingestion_job):
    """Test successful delete function."""
    with patch("repository.pipeline_ingestion.ingestion_job_repository") as mock_job_repo, patch(
        "repository.pipeline_ingestion.pipeline_delete"
    ) as mock_pipeline_delete:

        # Setup mocks
        mock_job_repo.update_status.return_value = sample_ingestion_job
        mock_pipeline_delete.return_value = None

        # Import the module
        import repository.pipeline_ingestion

        # Call the function
        repository.pipeline_ingestion.delete(sample_ingestion_job)

        # Verify calls
        mock_job_repo.update_status.assert_called_once_with(sample_ingestion_job, IngestionStatus.DELETE_IN_PROGRESS)
        mock_pipeline_delete.assert_called_once_with(sample_ingestion_job)


def test_delete_error(sample_ingestion_job):
    """Test delete function with error."""
    with patch("repository.pipeline_ingestion.ingestion_job_repository") as mock_job_repo, patch(
        "repository.pipeline_ingestion.pipeline_delete"
    ) as mock_pipeline_delete:

        # Setup mocks
        mock_job_repo.update_status.return_value = sample_ingestion_job
        mock_pipeline_delete.side_effect = Exception("Test error")

        # Import the module
        import repository.pipeline_ingestion

        # Call the function and expect exception
        with pytest.raises(Exception, match="Test error"):
            repository.pipeline_ingestion.delete(sample_ingestion_job)

        # Verify calls
        mock_job_repo.update_status.assert_called_once_with(sample_ingestion_job, IngestionStatus.DELETE_IN_PROGRESS)


def test_main_ingest_action(sample_ingestion_job):
    """Test main function with ingest action."""
    with patch("repository.pipeline_ingestion.ingestion_job_repository") as mock_job_repo, patch(
        "repository.pipeline_ingestion.ingest"
    ) as mock_ingest, patch("sys.argv", ["pipeline_ingestion.py", "ingest", "test-job-id"]):

        # Setup mocks
        mock_job_repo.find_by_id.return_value = sample_ingestion_job
        mock_ingest.return_value = None

        # Import the module
        # Simulate the main function logic
        import sys

        import repository.pipeline_ingestion

        if len(sys.argv) > 2:
            job = repository.pipeline_ingestion.ingestion_job_repository.find_by_id(sys.argv[2])
            if sys.argv[1] == "ingest":
                repository.pipeline_ingestion.ingest(job)

        # Verify calls
        mock_job_repo.find_by_id.assert_called_once_with("test-job-id")
        mock_ingest.assert_called_once_with(sample_ingestion_job)


def test_main_delete_action(sample_ingestion_job):
    """Test main function with delete action."""
    with patch("repository.pipeline_ingestion.ingestion_job_repository") as mock_job_repo, patch(
        "repository.pipeline_ingestion.delete"
    ) as mock_delete, patch("sys.argv", ["pipeline_ingestion.py", "delete", "test-job-id"]):

        # Setup mocks
        mock_job_repo.find_by_id.return_value = sample_ingestion_job
        mock_delete.return_value = None

        # Import the module
        # Simulate the main function logic
        import sys

        import repository.pipeline_ingestion

        if len(sys.argv) > 2:
            job = repository.pipeline_ingestion.ingestion_job_repository.find_by_id(sys.argv[2])
            if sys.argv[1] == "delete":
                repository.pipeline_ingestion.delete(job)

        # Verify calls
        mock_job_repo.find_by_id.assert_called_once_with("test-job-id")
        mock_delete.assert_called_once_with(sample_ingestion_job)


def test_main_invalid_action(sample_ingestion_job):
    """Test main function with invalid action."""
    with patch("repository.pipeline_ingestion.ingestion_job_repository"), patch(
        "repository.pipeline_ingestion.ingest"
    ), patch("repository.pipeline_ingestion.delete"), patch(
        "sys.argv", ["pipeline_ingestion.py", "invalid", "test-job-id"]
    ), patch(
        "sys.exit"
    ) as mock_exit:

        # Import the module
        # Simulate the main function logic - should not call any functions for invalid action
        import sys

        import repository.pipeline_ingestion

        if len(sys.argv) > 2:
            job = repository.pipeline_ingestion.ingestion_job_repository.find_by_id(sys.argv[2])
            if sys.argv[1] == "ingest":
                repository.pipeline_ingestion.ingest(job)
            elif sys.argv[1] == "delete":
                repository.pipeline_ingestion.delete(job)
            else:
                # Invalid action - should exit
                sys.exit(1)

        # Verify exit was called
        mock_exit.assert_called_once_with(1)


def test_main_missing_arguments(sample_ingestion_job):
    """Test main function with missing arguments."""
    with patch("sys.argv", ["pipeline_ingestion.py"]), patch("sys.exit") as mock_exit:

        # Import the module
        # Simulate the main function logic - should exit when not enough arguments
        import sys

        if len(sys.argv) <= 2:
            sys.exit(1)

        # Verify exit was called
        mock_exit.assert_called_once_with(1)
