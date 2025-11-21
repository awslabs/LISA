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

"""Tests for wait_for_collection_deletions Lambda function."""

import os
import sys
from unittest.mock import create_autospec, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../../../lambda"))


@pytest.fixture
def setup_env(monkeypatch):
    """Setup environment variables."""
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("LISA_INGESTION_JOB_TABLE_NAME", "test-job-table")


def test_all_deletions_complete(setup_env):
    """Test when all collection deletions are complete."""
    from repository.ingestion_job_repo import IngestionJobRepository
    from repository.state_machine.wait_for_collection_deletions import lambda_handler

    event = {"repositoryId": "repo1", "stackName": "test-stack"}

    with patch("repository.state_machine.wait_for_collection_deletions.IngestionJobRepository") as mock_repo_class:
        mock_repo = create_autospec(IngestionJobRepository, instance=True)
        mock_repo.find_pending_collection_deletions.return_value = []
        mock_repo_class.return_value = mock_repo

        result = lambda_handler(event, None)

        assert result["repositoryId"] == "repo1"
        assert result["stackName"] == "test-stack"
        assert result["allCollectionDeletionsComplete"] is True
        assert result["pendingDeletionCount"] == 0
        mock_repo.find_pending_collection_deletions.assert_called_once_with("repo1")


def test_deletions_still_pending(setup_env):
    """Test when collection deletions are still pending."""
    from models.domain_objects import IngestionJob, IngestionStatus, JobActionType
    from repository.ingestion_job_repo import IngestionJobRepository
    from repository.state_machine.wait_for_collection_deletions import lambda_handler

    event = {"repositoryId": "repo1", "stackName": "test-stack"}

    pending_job = IngestionJob(
        repository_id="repo1",
        collection_id="col1",
        s3_path="",
        status=IngestionStatus.DELETE_PENDING,
        job_type=JobActionType.COLLECTION_DELETION,
        collection_deletion=True,
    )

    with patch("repository.state_machine.wait_for_collection_deletions.IngestionJobRepository") as mock_repo_class:
        mock_repo = create_autospec(IngestionJobRepository, instance=True)
        mock_repo.find_pending_collection_deletions.return_value = [pending_job]
        mock_repo_class.return_value = mock_repo

        result = lambda_handler(event, None)

        assert result["repositoryId"] == "repo1"
        assert result["stackName"] == "test-stack"
        assert result["allCollectionDeletionsComplete"] is False
        assert result["pendingDeletionCount"] == 1
        mock_repo.find_pending_collection_deletions.assert_called_once_with("repo1")


def test_multiple_pending_deletions(setup_env):
    """Test when multiple collection deletions are pending."""
    from models.domain_objects import IngestionJob, IngestionStatus, JobActionType
    from repository.ingestion_job_repo import IngestionJobRepository
    from repository.state_machine.wait_for_collection_deletions import lambda_handler

    event = {"repositoryId": "repo1", "stackName": "test-stack"}

    pending_jobs = [
        IngestionJob(
            repository_id="repo1",
            collection_id=f"col{i}",
            s3_path="",
            status=IngestionStatus.DELETE_IN_PROGRESS,
            job_type=JobActionType.COLLECTION_DELETION,
            collection_deletion=True,
        )
        for i in range(3)
    ]

    with patch("repository.state_machine.wait_for_collection_deletions.IngestionJobRepository") as mock_repo_class:
        mock_repo = create_autospec(IngestionJobRepository, instance=True)
        mock_repo.find_pending_collection_deletions.return_value = pending_jobs
        mock_repo_class.return_value = mock_repo

        result = lambda_handler(event, None)

        assert result["repositoryId"] == "repo1"
        assert result["stackName"] == "test-stack"
        assert result["allCollectionDeletionsComplete"] is False
        assert result["pendingDeletionCount"] == 3
