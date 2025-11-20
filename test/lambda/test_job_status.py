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