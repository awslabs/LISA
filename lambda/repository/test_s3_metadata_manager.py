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

"""Unit tests for S3MetadataManager."""

import json
from unittest.mock import create_autospec, MagicMock

import pytest
from botocore.exceptions import ClientError
from repository.s3_metadata_manager import S3MetadataManager


@pytest.fixture
def mock_s3_client():
    """Mock S3 client."""
    return MagicMock()


@pytest.fixture
def mock_cloudwatch():
    """Mock CloudWatch client."""
    return MagicMock()


@pytest.fixture
def s3_metadata_manager(mock_cloudwatch):
    """Create S3MetadataManager instance with mocked CloudWatch."""
    return S3MetadataManager(cloudwatch_client=mock_cloudwatch)


@pytest.fixture
def sample_metadata():
    """Sample metadata content."""
    return {
        "metadataAttributes": {
            "collectionId": "col-123",
            "repositoryId": "repo-456",
            "tags": ["test", "sample"],
        }
    }


def test_upload_metadata_file_success(s3_metadata_manager, mock_s3_client, sample_metadata):
    """Test successful metadata file upload."""
    bucket = "test-bucket"
    document_key = "documents/test.pdf"

    result = s3_metadata_manager.upload_metadata_file(
        s3_client=mock_s3_client,
        bucket=bucket,
        document_key=document_key,
        metadata_content=sample_metadata,
    )

    # Verify S3 put_object was called
    assert mock_s3_client.put_object.called
    call_args = mock_s3_client.put_object.call_args
    assert call_args[1]["Bucket"] == bucket
    assert call_args[1]["Key"] == "documents/test.pdf.metadata.json"
    assert call_args[1]["ContentType"] == "application/json"

    # Verify result
    assert result == "documents/test.pdf.metadata.json"


def test_upload_metadata_file_with_metrics(s3_metadata_manager, mock_s3_client, sample_metadata, mock_cloudwatch):
    """Test metadata file upload emits CloudWatch metrics."""
    bucket = "test-bucket"
    document_key = "documents/test.pdf"
    repository_id = "repo-123"
    collection_id = "col-456"

    s3_metadata_manager.upload_metadata_file(
        s3_client=mock_s3_client,
        bucket=bucket,
        document_key=document_key,
        metadata_content=sample_metadata,
        repository_id=repository_id,
        collection_id=collection_id,
    )

    # Verify CloudWatch metric was emitted
    assert mock_cloudwatch.put_metric_data.called


def test_upload_metadata_file_access_denied(s3_metadata_manager, mock_s3_client, sample_metadata):
    """Test metadata file upload with access denied error."""
    mock_s3_client.put_object.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "PutObject"
    )

    with pytest.raises(ClientError):
        s3_metadata_manager.upload_metadata_file(
            s3_client=mock_s3_client,
            bucket="test-bucket",
            document_key="documents/test.pdf",
            metadata_content=sample_metadata,
        )


def test_upload_metadata_file_retry_on_transient_error(s3_metadata_manager, mock_s3_client, sample_metadata):
    """Test metadata file upload retries on transient errors."""
    # First call fails, second succeeds
    mock_s3_client.put_object.side_effect = [
        ClientError({"Error": {"Code": "ServiceUnavailable", "Message": "Service Unavailable"}}, "PutObject"),
        None,  # Success
    ]

    result = s3_metadata_manager.upload_metadata_file(
        s3_client=mock_s3_client,
        bucket="test-bucket",
        document_key="documents/test.pdf",
        metadata_content=sample_metadata,
    )

    # Verify retry happened
    assert mock_s3_client.put_object.call_count == 2
    assert result == "documents/test.pdf.metadata.json"


def test_delete_metadata_file_success(s3_metadata_manager, mock_s3_client):
    """Test successful metadata file deletion."""
    bucket = "test-bucket"
    document_key = "documents/test.pdf"

    s3_metadata_manager.delete_metadata_file(s3_client=mock_s3_client, bucket=bucket, document_key=document_key)

    # Verify S3 delete_object was called
    assert mock_s3_client.delete_object.called
    call_args = mock_s3_client.delete_object.call_args
    assert call_args[1]["Bucket"] == bucket
    assert call_args[1]["Key"] == "documents/test.pdf.metadata.json"


def test_delete_metadata_file_not_found(s3_metadata_manager, mock_s3_client):
    """Test metadata file deletion when file doesn't exist (idempotent)."""
    mock_s3_client.delete_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}, "DeleteObject"
    )

    # Should not raise exception
    s3_metadata_manager.delete_metadata_file(
        s3_client=mock_s3_client, bucket="test-bucket", document_key="documents/test.pdf"
    )


def test_delete_metadata_file_with_metrics(s3_metadata_manager, mock_s3_client, mock_cloudwatch):
    """Test metadata file deletion emits CloudWatch metrics."""
    bucket = "test-bucket"
    document_key = "documents/test.pdf"
    repository_id = "repo-123"
    collection_id = "col-456"

    s3_metadata_manager.delete_metadata_file(
        s3_client=mock_s3_client,
        bucket=bucket,
        document_key=document_key,
        repository_id=repository_id,
        collection_id=collection_id,
    )

    # Verify CloudWatch metric was emitted
    assert mock_cloudwatch.put_metric_data.called


def test_batch_upload_metadata_success(s3_metadata_manager, mock_s3_client, sample_metadata):
    """Test batch upload of multiple metadata files."""
    bucket = "test-bucket"
    documents = [
        ("documents/test1.pdf", sample_metadata),
        ("documents/test2.pdf", sample_metadata),
        ("documents/test3.pdf", sample_metadata),
    ]

    result = s3_metadata_manager.batch_upload_metadata(s3_client=mock_s3_client, bucket=bucket, documents=documents)

    # Verify all uploads succeeded
    assert len(result) == 3
    assert mock_s3_client.put_object.call_count == 3


def test_batch_upload_metadata_partial_failure(s3_metadata_manager, mock_s3_client, sample_metadata):
    """Test batch upload continues on individual failures."""
    bucket = "test-bucket"
    documents = [
        ("documents/test1.pdf", sample_metadata),
        ("documents/test2.pdf", sample_metadata),
        ("documents/test3.pdf", sample_metadata),
    ]

    # Second upload fails
    mock_s3_client.put_object.side_effect = [
        None,  # Success
        ClientError({"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "PutObject"),
        None,  # Success
    ]

    result = s3_metadata_manager.batch_upload_metadata(s3_client=mock_s3_client, bucket=bucket, documents=documents)

    # Verify 2 out of 3 succeeded
    assert len(result) == 2


def test_batch_delete_metadata_success(s3_metadata_manager, mock_s3_client):
    """Test batch deletion of multiple metadata files."""
    bucket = "test-bucket"
    document_keys = ["documents/test1.pdf", "documents/test2.pdf", "documents/test3.pdf"]

    result = s3_metadata_manager.batch_delete_metadata(
        s3_client=mock_s3_client, bucket=bucket, document_keys=document_keys
    )

    # Verify all deletions succeeded
    assert result == 3
    assert mock_s3_client.delete_object.call_count == 3


def test_batch_delete_metadata_partial_failure(s3_metadata_manager, mock_s3_client):
    """Test batch deletion continues on individual failures."""
    bucket = "test-bucket"
    document_keys = ["documents/test1.pdf", "documents/test2.pdf", "documents/test3.pdf"]

    # Second deletion fails with NoSuchKey (idempotent - counts as success)
    # Third deletion fails with AccessDenied (logs warning but continues)
    mock_s3_client.delete_object.side_effect = [
        None,  # Success
        ClientError({"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}, "DeleteObject"),
        ClientError({"Error": {"Code": "AccessDenied", "Message": "Access Denied"}}, "DeleteObject"),
    ]

    result = s3_metadata_manager.batch_delete_metadata(
        s3_client=mock_s3_client, bucket=bucket, document_keys=document_keys
    )

    # All 3 count as "deleted" (first succeeds, second is idempotent, third logs warning but continues)
    assert result == 3
