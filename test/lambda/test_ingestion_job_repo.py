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
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))


@pytest.fixture
def ingestion_repo(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("LISA_INGESTION_JOB_TABLE_NAME", "test-table")

    from repository.ingestion_job_repo import IngestionJobRepository

    return IngestionJobRepository()


def test_get_batch_job_status(ingestion_repo):
    mock_batch = MagicMock()
    mock_batch.describe_jobs.return_value = {"jobs": [{"status": "RUNNING"}]}

    ingestion_repo._batch_client = mock_batch
    status = ingestion_repo.get_batch_job_status("job1")
    assert status == "RUNNING"


def test_find_batch_job_for_document(ingestion_repo):
    mock_batch = MagicMock()
    mock_batch.list_jobs.return_value = {"jobSummaryList": [{"jobId": "batch1", "jobName": "document-ingest-doc1-123"}]}

    ingestion_repo._batch_client = mock_batch
    result = ingestion_repo.find_batch_job_for_document("doc1", "queue1")
    assert result is not None
    assert result["jobId"] == "batch1"


# Additional coverage tests
def test_ingestion_job_repo_save(ingestion_repo):
    from unittest.mock import patch

    from models.domain_objects import IngestionJob

    with patch("repository.ingestion_job_repo._get_ingestion_job_table") as mock_table:
        job = IngestionJob(
            id="job1", repository_id="repo1", collection_id="col1", s3_path="s3://bucket/key", username="user1"
        )
        ingestion_repo.save(job)
        mock_table.return_value.put_item.assert_called_once()


def test_ingestion_job_repo_find_by_id(ingestion_repo):
    from unittest.mock import patch

    with patch("repository.ingestion_job_repo._get_ingestion_job_table") as mock_table:
        mock_table.return_value.get_item.return_value = {
            "Item": {
                "id": "job1",
                "repository_id": "repo1",
                "collection_id": "col1",
                "s3_path": "s3://bucket/key",
                "username": "user1",
            }
        }
        result = ingestion_repo.find_by_id("job1")
        assert result.id == "job1"


def test_ingestion_job_repo_find_by_path(ingestion_repo):
    from unittest.mock import patch

    with patch("repository.ingestion_job_repo._get_ingestion_job_table") as mock_table:
        mock_table.return_value.query.return_value = {
            "Items": [
                {
                    "id": "job1",
                    "repository_id": "repo1",
                    "collection_id": "col1",
                    "s3_path": "s3://bucket/key",
                    "username": "user1",
                }
            ]
        }
        results = ingestion_repo.find_by_path("s3://bucket/key")
        assert len(results) == 1


def test_ingestion_job_repo_find_by_document(ingestion_repo):
    from unittest.mock import patch

    with patch("repository.ingestion_job_repo._get_ingestion_job_table") as mock_table:
        mock_table.return_value.query.return_value = {
            "Items": [
                {
                    "id": "job1",
                    "document_id": "doc1",
                    "repository_id": "repo1",
                    "collection_id": "col1",
                    "s3_path": "s3://bucket/key",
                    "username": "user1",
                }
            ]
        }
        result = ingestion_repo.find_by_document("doc1")
        assert result.id == "job1"


def test_ingestion_job_repo_find_by_document_none(ingestion_repo):
    from unittest.mock import patch

    with patch("repository.ingestion_job_repo._get_ingestion_job_table") as mock_table:
        mock_table.return_value.query.return_value = {"Items": []}
        result = ingestion_repo.find_by_document("doc1")
        assert result is None


def test_ingestion_job_repo_update_status(ingestion_repo):
    from unittest.mock import patch

    from models.domain_objects import IngestionJob

    with patch("repository.ingestion_job_repo._get_ingestion_job_table") as mock_table:
        mock_table.return_value.update_item.return_value = {}
        job = IngestionJob(
            id="job1", repository_id="repo1", collection_id="col1", s3_path="s3://bucket/key", username="user1"
        )
        result = ingestion_repo.update_status(job, "PENDING")
        assert result.status == "PENDING"


def test_ingestion_job_repo_get_batch_job_status_none(ingestion_repo):
    mock_batch = MagicMock()
    mock_batch.describe_jobs.return_value = {"jobs": []}
    ingestion_repo._batch_client = mock_batch

    status = ingestion_repo.get_batch_job_status("job123")
    assert status is None


def test_ingestion_job_repo_find_batch_job_not_found(ingestion_repo):
    mock_batch = MagicMock()
    mock_batch.list_jobs.return_value = {"jobSummaryList": []}
    ingestion_repo._batch_client = mock_batch

    result = ingestion_repo.find_batch_job_for_document("doc1", "queue")
    assert result is None


def test_ingestion_job_repo_list_jobs_by_repository(ingestion_repo):
    from unittest.mock import patch

    with patch("repository.ingestion_job_repo._get_ingestion_job_table") as mock_table:
        mock_table.return_value.query.return_value = {
            "Items": [
                {
                    "id": "job1",
                    "repository_id": "repo1",
                    "collection_id": "col1",
                    "s3_path": "s3://bucket/key",
                    "username": "user1",
                }
            ]
        }
        jobs, last_key = ingestion_repo.list_jobs_by_repository("repo1", "user1", True, 1, 10)
        assert len(jobs) == 1


def test_ingestion_job_repo_list_jobs_non_admin(ingestion_repo):
    from unittest.mock import patch

    with patch("repository.ingestion_job_repo._get_ingestion_job_table") as mock_table:
        mock_table.return_value.query.return_value = {
            "Items": [
                {
                    "id": "job1",
                    "repository_id": "repo1",
                    "collection_id": "col1",
                    "s3_path": "s3://bucket/key",
                    "username": "user1",
                }
            ]
        }
        jobs, _ = ingestion_repo.list_jobs_by_repository("repo1", "user1", False, 1, 10)
        assert len(jobs) == 1
