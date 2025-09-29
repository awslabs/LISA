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
os.environ["AWS_REGION"] = "us-east-1"

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


def test_extract_text_by_content_type_pdf():
    """Test _extract_text_by_content_type with PDF file."""
    from utilities.file_processing import _extract_text_by_content_type

    mock_s3_object = {"Body": BytesIO(b"mock pdf content")}

    with patch("utilities.file_processing._extract_pdf_content") as mock_extract:
        mock_extract.return_value = "Extracted PDF text"

        result = _extract_text_by_content_type("pdf", mock_s3_object)

        assert result == "Extracted PDF text"
        mock_extract.assert_called_once_with(mock_s3_object)


def test_extract_text_by_content_type_docx():
    """Test _extract_text_by_content_type with DOCX file."""
    from utilities.file_processing import _extract_text_by_content_type

    mock_s3_object = {"Body": BytesIO(b"mock docx content")}

    with patch("utilities.file_processing._extract_docx_content") as mock_extract:
        mock_extract.return_value = "Extracted DOCX text"

        result = _extract_text_by_content_type("docx", mock_s3_object)

        assert result == "Extracted DOCX text"
        mock_extract.assert_called_once_with(mock_s3_object)


def test_extract_text_by_content_type_txt():
    """Test _extract_text_by_content_type with TXT file."""
    from utilities.file_processing import _extract_text_by_content_type

    mock_s3_object = {"Body": BytesIO(b"mock text content")}

    with patch("utilities.file_processing._extract_text_content") as mock_extract:
        mock_extract.return_value = "Extracted text content"

        result = _extract_text_by_content_type("txt", mock_s3_object)

        assert result == "Extracted text content"
        mock_extract.assert_called_once_with(mock_s3_object)


def test_extract_text_by_content_type_unsupported():
    """Test _extract_text_by_content_type with unsupported file type."""
    from utilities.file_processing import _extract_text_by_content_type

    mock_s3_object = {"Body": BytesIO(b"mock content")}

    with pytest.raises(RagUploadException, match="Unsupported file type"):
        _extract_text_by_content_type("unsupported", mock_s3_object)


def test_generate_chunks_invalid_chunk_size():
    """Test _generate_chunks with invalid chunk size."""
    docs = [Document(page_content="Test content", metadata={})]

    with pytest.raises(RagUploadException, match="Invalid chunk size"):
        _generate_chunks(docs, chunk_size=50, chunk_overlap=51)  # chunk_size < 100

    with pytest.raises(RagUploadException, match="Invalid chunk size"):
        _generate_chunks(docs, chunk_size=15000, chunk_overlap=51)  # chunk_size > 10000


def test_generate_chunks_invalid_chunk_overlap():
    """Test _generate_chunks with invalid chunk overlap."""
    docs = [Document(page_content="Test content", metadata={})]

    with pytest.raises(RagUploadException, match="Invalid chunk overlap"):
        _generate_chunks(docs, chunk_size=512, chunk_overlap=-1)  # negative overlap

    with pytest.raises(RagUploadException, match="Invalid chunk overlap"):
        _generate_chunks(docs, chunk_size=512, chunk_overlap=512)  # overlap >= chunk_size


def test_generate_chunks_with_none_values():
    """Test _generate_chunks with None chunk_size and chunk_overlap."""
    docs = [Document(page_content="Test content", metadata={})]

    with patch.dict(os.environ, {"CHUNK_SIZE": "256", "CHUNK_OVERLAP": "25"}):
        result = _generate_chunks(docs, chunk_size=None, chunk_overlap=None)
        assert len(result) > 0


def test_extract_pdf_content_error():
    """Test _extract_pdf_content with PDF read error."""
    from pypdf.errors import PdfReadError
    from utilities.file_processing import _extract_pdf_content

    mock_s3_object = {"Body": BytesIO(b"invalid pdf content")}

    with patch("utilities.file_processing.PdfReader") as mock_reader:
        mock_reader.side_effect = PdfReadError("Invalid PDF")

        with pytest.raises(PdfReadError):
            _extract_pdf_content(mock_s3_object)


def test_extract_pdf_content_success():
    """Test _extract_pdf_content with valid PDF."""
    from utilities.file_processing import _extract_pdf_content

    mock_s3_object = {"Body": BytesIO(b"mock pdf content")}

    with patch("utilities.file_processing.PdfReader") as mock_reader:
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 content"
        mock_reader.return_value.pages = [mock_page]

        result = _extract_pdf_content(mock_s3_object)
        assert result == "Page 1 content"


def test_extract_docx_content_success():
    """Test _extract_docx_content with valid DOCX."""
    from utilities.file_processing import _extract_docx_content

    mock_s3_object = {"Body": BytesIO(b"mock docx content")}

    with patch("utilities.file_processing.docx.Document") as mock_doc:
        mock_para = MagicMock()
        mock_para.text = "Paragraph content"
        mock_doc.return_value.paragraphs = [mock_para]

        result = _extract_docx_content(mock_s3_object)
        assert result == "Paragraph content"


def test_extract_text_content_success():
    """Test _extract_text_content with valid text."""
    from utilities.file_processing import _extract_text_content

    mock_s3_object = {"Body": BytesIO(b"test text content")}

    result = _extract_text_content(mock_s3_object)
    assert result == "test text content"


def test_generate_chunks_s3_error(sample_ingestion_job):
    """Test generate_chunks with S3 ClientError."""
    from botocore.exceptions import ClientError

    job = sample_ingestion_job
    job.s3_path = "s3://test-bucket/test-key.txt"

    with patch("utilities.file_processing.s3") as mock_s3:
        mock_s3.get_object.side_effect = ClientError(
            error_response={"Error": {"Code": "NoSuchKey"}}, operation_name="GetObject"
        )

        with pytest.raises(ClientError):
            generate_chunks(job)


def test_generate_chunks_unrecognized_strategy(sample_ingestion_job):
    """Test generate_chunks with unrecognized chunk strategy."""
    from models.domain_objects import ChunkingStrategyType, FixedChunkingStrategy

    job = sample_ingestion_job
    job.s3_path = "s3://test-bucket/test-key.txt"

    # Create a mock chunking strategy with an invalid type by directly setting the attribute
    job.chunk_strategy = FixedChunkingStrategy(type=ChunkingStrategyType.FIXED, size=512, overlap=51)
    job.chunk_strategy.type = "INVALID_TYPE"  # Override the type after creation

    with patch("utilities.file_processing.s3") as mock_s3:
        mock_s3.get_object.return_value = {"Body": BytesIO(b"test content")}

        with pytest.raises(Exception, match="Unrecognized chunk strategy"):
            generate_chunks(job)


def test_generate_fixed_chunks_with_metadata(sample_ingestion_job):
    """Test generate_fixed_chunks updates metadata with part numbers."""
    from utilities.file_processing import generate_fixed_chunks

    job = sample_ingestion_job
    job.s3_path = "s3://test-bucket/test-key.txt"

    mock_s3_object = {"Body": BytesIO(b"test content for chunking " * 100)}

    with patch("utilities.file_processing._extract_text_by_content_type") as mock_extract:
        mock_extract.return_value = "test content for chunking " * 100

        result = generate_fixed_chunks(job, "txt", mock_s3_object)

        assert len(result) > 1
        for i, doc in enumerate(result):
            assert doc.metadata["part"] == i + 1
            assert doc.metadata["source"] == job.s3_path
            assert doc.metadata["name"] == "test-key.txt"
