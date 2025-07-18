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

"""Test file_processing module."""

import os
import sys
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../"))

# Set up mock AWS credentials
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

from langchain_core.documents import Document

# Import after setting up environment
from models.domain_objects import (
    ChunkingStrategyType,
    FixedChunkingStrategy,
    IngestionJob,
    IngestionStatus,
    IngestionType,
)
from utilities.exceptions import RagUploadException
from utilities.file_processing import _generate_chunks, generate_chunks


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


def test_generate_chunks_success(sample_ingestion_job):
    """Test _generate_chunks function."""
    docs = [Document(page_content="This is a test document with some content to split into chunks.", metadata={})]
    # Use valid chunk_size and chunk_overlap
    result = _generate_chunks(docs, chunk_size=512, chunk_overlap=51)
    assert len(result) > 0
    assert all(isinstance(doc, Document) for doc in result)


def test_generate_chunks_invalid_s3_path(sample_ingestion_job):
    """Test generate_chunks with invalid S3 path."""
    job = sample_ingestion_job
    job.s3_path = "invalid-path"

    with pytest.raises(RagUploadException, match="Invalid S3 path format"):
        generate_chunks(job)


def test_generate_chunks_success_with_valid_path(sample_ingestion_job):
    """Test generate_chunks with valid S3 path."""
    # Use a supported file extension for the test
    sample_ingestion_job.s3_path = "s3://test-bucket/test-key.txt"
    with patch("utilities.file_processing.boto3.client") as mock_client, patch(
        "utilities.file_processing.s3"
    ) as mock_s3_global:

        # Setup mocks
        mock_s3 = MagicMock()
        mock_client.return_value = mock_s3
        mock_s3_global.get_object.return_value = {"Body": BytesIO(b"test content")}

        # Call the function
        result = generate_chunks(sample_ingestion_job)

        # Verify calls
        mock_s3_global.get_object.assert_called_once_with(Bucket="test-bucket", Key="test-key.txt")
        assert isinstance(result, list)
        assert all(isinstance(doc, Document) for doc in result)


def test_generate_fixed_chunks_with_none_values():
    """Test _generate_chunks with None values in documents."""
    docs = [Document(page_content="Valid content", metadata={}), Document(page_content="", metadata={})]

    result = _generate_chunks(docs, chunk_size=512, chunk_overlap=51)

    # Should handle empty content
    assert len(result) > 0
    assert all(doc.page_content for doc in result)


def test_generate_chunks_with_large_content():
    """Test _generate_chunks with content larger than chunk size."""
    long_content = "This is a very long document with lots of content. " * 100
    docs = [Document(page_content=long_content, metadata={})]

    result = _generate_chunks(docs, chunk_size=512, chunk_overlap=51)

    assert len(result) > 1  # Should create multiple chunks
    assert all(len(doc.page_content) <= 512 for doc in result)


def test_generate_chunks_with_overlap():
    """Test _generate_chunks with overlap."""
    content = "This is a test document with some content to split into chunks. " * 20  # Make it longer
    docs = [Document(page_content=content, metadata={})]

    result = _generate_chunks(docs, chunk_size=512, chunk_overlap=51)

    assert len(result) > 1
    # Check that chunks have some overlap by looking for common text
    if len(result) > 1:
        first_chunk = result[0].page_content
        second_chunk = result[1].page_content
        # Find common text between chunks (overlap)
        common_text = ""
        for i in range(len(first_chunk)):
            if first_chunk[i:] in second_chunk:
                common_text = first_chunk[i:]
                break
        # Should have some overlap
        assert len(common_text) > 0


def test_generate_chunks_empty_documents():
    """Test _generate_chunks with empty documents list."""
    result = _generate_chunks([], chunk_size=512, chunk_overlap=51)

    assert result == []


def test_generate_chunks_single_document():
    """Test _generate_chunks with single document."""
    docs = [Document(page_content="Single document content", metadata={})]

    result = _generate_chunks(docs, chunk_size=512, chunk_overlap=51)

    assert len(result) == 1
    assert result[0].page_content == "Single document content"


def test_generate_chunks_preserves_metadata():
    """Test _generate_chunks preserves document metadata."""
    metadata = {"source": "test-source", "author": "test-author"}
    docs = [Document(page_content="Test content", metadata=metadata)]

    result = _generate_chunks(docs, chunk_size=512, chunk_overlap=51)

    assert len(result) == 1
    assert result[0].metadata == metadata
