#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

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
    """Test is_terminal_status function"""
    from repository.job_status import is_terminal_status

    assert is_terminal_status(IngestionStatus.INGESTION_COMPLETED) is True
    assert is_terminal_status(IngestionStatus.INGESTION_FAILED) is True
    assert is_terminal_status(IngestionStatus.DELETE_COMPLETED) is True
    assert is_terminal_status(IngestionStatus.DELETE_FAILED) is True
    
    assert is_terminal_status(IngestionStatus.INGESTION_PENDING) is False
    assert is_terminal_status(IngestionStatus.INGESTION_IN_PROGRESS) is False
    assert is_terminal_status(IngestionStatus.DELETE_PENDING) is False
    assert is_terminal_status(IngestionStatus.DELETE_IN_PROGRESS) is False


def test_is_success_status():
    """Test is_success_status function"""
    from repository.job_status import is_success_status

    assert is_success_status(IngestionStatus.INGESTION_COMPLETED) is True
    assert is_success_status(IngestionStatus.DELETE_COMPLETED) is True
    
    assert is_success_status(IngestionStatus.INGESTION_FAILED) is False
    assert is_success_status(IngestionStatus.DELETE_FAILED) is False
    assert is_success_status(IngestionStatus.INGESTION_PENDING) is False
