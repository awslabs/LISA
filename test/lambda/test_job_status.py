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

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

from models.domain_objects import IngestionStatus


@pytest.fixture(autouse=True)
def setup_env(monkeypatch):
    """Setup environment variables for all tests."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")


def test_is_terminal_status():
    """Test is_terminal method on IngestionStatus enum"""
    assert IngestionStatus.INGESTION_COMPLETED.is_terminal() is True
    assert IngestionStatus.INGESTION_FAILED.is_terminal() is True
    assert IngestionStatus.DELETE_COMPLETED.is_terminal() is True
    assert IngestionStatus.DELETE_FAILED.is_terminal() is True

    assert IngestionStatus.INGESTION_PENDING.is_terminal() is False
    assert IngestionStatus.INGESTION_IN_PROGRESS.is_terminal() is False
    assert IngestionStatus.DELETE_PENDING.is_terminal() is False
    assert IngestionStatus.DELETE_IN_PROGRESS.is_terminal() is False


def test_is_success_status():
    """Test is_success method on IngestionStatus enum"""
    assert IngestionStatus.INGESTION_COMPLETED.is_success() is True
    assert IngestionStatus.DELETE_COMPLETED.is_success() is True

    assert IngestionStatus.INGESTION_FAILED.is_success() is False
    assert IngestionStatus.DELETE_FAILED.is_success() is False
    assert IngestionStatus.INGESTION_PENDING.is_success() is False
"""Unit tests for job status models."""

import pytest
from repository.job_status import JobStatus


class TestJobStatus:
    """Test JobStatus Pydantic model."""

    def test_job_status_creation_with_valid_data(self):
        """Test creating a JobStatus with valid data."""
        job_data = {
            "status": "completed",
            "document": "test-document.pdf",
            "auto": True,
            "created_date": "2025-01-15T10:00:00Z",
        }

        job_status = JobStatus(**job_data)

        assert job_status.status == "completed"
        assert job_status.document == "test-document.pdf"
        assert job_status.auto is True
        assert job_status.created_date == "2025-01-15T10:00:00Z"

    def test_job_status_creation_with_different_status(self):
        """Test creating a JobStatus with different status values."""
        job_data = {
            "status": "running",
            "document": "another-document.txt",
            "auto": False,
            "created_date": "2025-01-15T11:30:00Z",
        }

        job_status = JobStatus(**job_data)

        assert job_status.status == "running"
        assert job_status.document == "another-document.txt"
        assert job_status.auto is False
        assert job_status.created_date == "2025-01-15T11:30:00Z"

    def test_job_status_model_dump(self):
        """Test serializing JobStatus to dictionary."""
        job_data = {
            "status": "failed",
            "document": "error-document.docx",
            "auto": True,
            "created_date": "2025-01-15T12:00:00Z",
        }

        job_status = JobStatus(**job_data)
        result = job_status.model_dump()

        assert result == job_data

    def test_job_status_model_validation(self):
        """Test JobStatus model validation with missing fields."""
        # Test with missing required field
        with pytest.raises(ValueError):
            JobStatus(
                status="completed",
                document="test.pdf",
                auto=True,
                # missing created_date
            )

    def test_job_status_field_types(self):
        """Test JobStatus with different field types."""
        job_data = {
            "status": "pending",
            "document": "test.pdf",
            "auto": "true",  # String that should be converted to bool
            "created_date": "2025-01-15T09:00:00Z",
        }

        job_status = JobStatus(**job_data)

        assert job_status.status == "pending"
        assert job_status.document == "test.pdf"
        assert job_status.auto is True  # Should be converted to boolean
        assert job_status.created_date == "2025-01-15T09:00:00Z"
