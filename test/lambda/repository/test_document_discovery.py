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

"""Unit tests for Bedrock KB document discovery."""

from unittest.mock import MagicMock, create_autospec

import pytest

from models.domain_objects import IngestionType
from utilities.bedrock_kb import ingest_bedrock_s3_documents


class TestDocumentDiscovery:
    """Test document discovery for Bedrock KB."""

    def test_discover_documents_empty_bucket(self):
        """Test discovery with empty S3 bucket."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {}  # No Contents key

        mock_job_repo = MagicMock()
        mock_service = MagicMock()

        discovered, skipped = ingest_bedrock_s3_documents(
            s3_client=mock_s3,
            ingestion_job_repository=mock_job_repo,
            ingestion_service=mock_service,
            repository_id="repo1",
            collection_id="col1",
            s3_bucket="empty-bucket",
            embedding_model="model1",
        )

        assert discovered == 0
        assert skipped == 0
        assert mock_job_repo.save.call_count == 0
        assert mock_service.submit_create_job.call_count == 0

    def test_discover_documents_with_files(self):
        """Test discovery with files in S3 bucket."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "doc1.pdf"},
                {"Key": "doc2.pdf"},
                {"Key": "doc3.pdf"},
            ]
        }

        mock_job_repo = MagicMock()
        mock_service = MagicMock()

        discovered, skipped = ingest_bedrock_s3_documents(
            s3_client=mock_s3,
            ingestion_job_repository=mock_job_repo,
            ingestion_service=mock_service,
            repository_id="repo1",
            collection_id="col1",
            s3_bucket="test-bucket",
            embedding_model="model1",
        )

        assert discovered == 3
        assert skipped == 0
        assert mock_job_repo.save.call_count == 1
        assert mock_service.submit_create_job.call_count == 1

        # Verify job has correct ingestion_type
        saved_job = mock_job_repo.save.call_args[0][0]
        assert saved_job.ingestion_type == IngestionType.EXISTING
        assert saved_job.username == "system"
        assert len(saved_job.s3_paths) == 3

    def test_discover_documents_skips_metadata(self):
        """Test that metadata files are skipped."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {
            "Contents": [
                {"Key": "doc1.pdf"},
                {"Key": "doc1.pdf.metadata.json"},  # Should be skipped
                {"Key": "doc2.pdf"},
                {"Key": "folder/"},  # Should be skipped
            ]
        }

        mock_job_repo = MagicMock()
        mock_service = MagicMock()

        discovered, skipped = ingest_bedrock_s3_documents(
            s3_client=mock_s3,
            ingestion_job_repository=mock_job_repo,
            ingestion_service=mock_service,
            repository_id="repo1",
            collection_id="col1",
            s3_bucket="test-bucket",
            embedding_model="model1",
        )

        assert discovered == 2
        assert skipped == 2

        # Verify only valid documents in job
        saved_job = mock_job_repo.save.call_args[0][0]
        assert len(saved_job.s3_paths) == 2
        assert "s3://test-bucket/doc1.pdf" in saved_job.s3_paths
        assert "s3://test-bucket/doc2.pdf" in saved_job.s3_paths

    def test_discover_documents_batching(self):
        """Test that large numbers of documents are batched."""
        # Create 250 documents (should create 3 batches: 100, 100, 50)
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.return_value = {
            "Contents": [{"Key": f"doc{i}.pdf"} for i in range(250)]
        }

        mock_job_repo = MagicMock()
        mock_service = MagicMock()

        discovered, skipped = ingest_bedrock_s3_documents(
            s3_client=mock_s3,
            ingestion_job_repository=mock_job_repo,
            ingestion_service=mock_service,
            repository_id="repo1",
            collection_id="col1",
            s3_bucket="test-bucket",
            embedding_model="model1",
        )

        assert discovered == 250
        assert skipped == 0
        assert mock_job_repo.save.call_count == 3  # 3 batches
        assert mock_service.submit_create_job.call_count == 3

        # Verify batch sizes
        all_jobs = [call[0][0] for call in mock_job_repo.save.call_args_list]
        assert len(all_jobs[0].s3_paths) == 100
        assert len(all_jobs[1].s3_paths) == 100
        assert len(all_jobs[2].s3_paths) == 50

        # Verify all jobs have EXISTING type
        for job in all_jobs:
            assert job.ingestion_type == IngestionType.EXISTING

    def test_discover_documents_handles_errors(self):
        """Test that errors during discovery are handled gracefully."""
        mock_s3 = MagicMock()
        mock_s3.list_objects_v2.side_effect = Exception("S3 error")

        mock_job_repo = MagicMock()
        mock_service = MagicMock()

        # Should not raise, but return (0, 0)
        discovered, skipped = ingest_bedrock_s3_documents(
            s3_client=mock_s3,
            ingestion_job_repository=mock_job_repo,
            ingestion_service=mock_service,
            repository_id="repo1",
            collection_id="col1",
            s3_bucket="error-bucket",
            embedding_model="model1",
        )

        assert discovered == 0
        assert skipped == 0
        assert mock_job_repo.save.call_count == 0
