#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import sys
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))


@pytest.fixture
def ingestion_repo(monkeypatch):
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("LISA_INGESTION_JOB_TABLE_NAME", "test-table")
    
    from repository.ingestion_job_repo import IngestionJobRepository
    return IngestionJobRepository()


def test_get_batch_job_status(ingestion_repo):
    mock_batch = MagicMock()
    mock_batch.describe_jobs.return_value = {
        "jobs": [{"status": "RUNNING"}]
    }
    
    ingestion_repo._batch_client = mock_batch
    status = ingestion_repo.get_batch_job_status("job1")
    assert status == "RUNNING"


def test_find_batch_job_for_document(ingestion_repo):
    mock_batch = MagicMock()
    mock_batch.list_jobs.return_value = {
        "jobSummaryList": [
            {"jobId": "batch1", "jobName": "document-ingest-doc1-123"}
        ]
    }
    
    ingestion_repo._batch_client = mock_batch
    result = ingestion_repo.find_batch_job_for_document("doc1", "queue1")
    assert result is not None
    assert result["jobId"] == "batch1"
