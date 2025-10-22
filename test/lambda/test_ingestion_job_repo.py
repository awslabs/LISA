#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import os
import sys
from unittest.mock import MagicMock, patch, Mock
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from models.domain_objects import IngestionJob, IngestionStatus


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Setup environment variables for all tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("LISA_INGESTION_JOB_TABLE_NAME", "test-table")


def test_ingestion_job_repo_save():
    """Test ingestion job repository save"""
    with patch("repository.ingestion_job_repo._get_ingestion_job_table") as mock_table_fn:
        mock_table = Mock()
        mock_table_fn.return_value = mock_table
        
        from repository.ingestion_job_repo import IngestionJobRepository
        repo = IngestionJobRepository()
        
        job = IngestionJob(
            id="job-1",
            repository_id="repo",
            collection_id="coll",
            s3_path="s3://bucket/key",
            status=IngestionStatus.INGESTION_PENDING,
        )
        
        mock_table.put_item.return_value = {}
        repo.save(job)
        
        mock_table.put_item.assert_called_once()


def test_ingestion_job_repo_get():
    """Test ingestion job repository get"""
    with patch("repository.ingestion_job_repo._get_ingestion_job_table") as mock_table_fn:
        mock_table = Mock()
        mock_table_fn.return_value = mock_table
        
        from repository.ingestion_job_repo import IngestionJobRepository
        repo = IngestionJobRepository()
        
        mock_table.get_item.return_value = {
            "Item": {
                "id": "job-1",
                "repository_id": "repo",
                "collection_id": "coll",
                "s3_path": "s3://bucket/key",
                "status": "INGESTION_PENDING",
                "created_date": "2025-01-01T00:00:00Z",
            }
        }
        
        result = repo.find_by_id("job-1")
        
        assert result is not None
        mock_table.get_item.assert_called_once()


def test_ingestion_job_repo_list():
    """Test ingestion job repository list"""
    with patch("repository.ingestion_job_repo._get_ingestion_job_table") as mock_table_fn:
        mock_table = Mock()
        mock_table_fn.return_value = mock_table
        
        from repository.ingestion_job_repo import IngestionJobRepository
        repo = IngestionJobRepository()
        
        mock_table.query.return_value = {
            "Items": [
                {
                    "id": "job-1",
                    "repository_id": "repo",
                    "collection_id": "coll",
                    "s3_path": "s3://bucket/key",
                    "status": "INGESTION_COMPLETED",
                    "created_date": "2025-01-01T00:00:00Z",
                }
            ]
        }
        
        result, key = repo.list_jobs_by_repository("repo", "user", True)
        
        assert len(result) == 1
        mock_table.query.assert_called_once()


def test_ingestion_job_repo_update_status():
    """Test ingestion job repository update status"""
    with patch("repository.ingestion_job_repo._get_ingestion_job_table") as mock_table_fn:
        mock_table = Mock()
        mock_table_fn.return_value = mock_table
        
        from repository.ingestion_job_repo import IngestionJobRepository
        repo = IngestionJobRepository()
        
        job = IngestionJob(
            id="job-1",
            repository_id="repo",
            collection_id="coll",
            s3_path="s3://bucket/key",
            status=IngestionStatus.INGESTION_PENDING,
        )
        
        mock_table.update_item.return_value = {}
        repo.update_status(job, IngestionStatus.INGESTION_COMPLETED)
        
        mock_table.update_item.assert_called_once()
