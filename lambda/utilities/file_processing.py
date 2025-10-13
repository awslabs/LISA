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

"""Helper functions to parse documents for ingestion into RAG vector store."""
import logging
import os
from io import BytesIO
from typing import Any, List
from urllib.parse import urlparse

import boto3
import docx
from botocore.exceptions import ClientError
from langchain_core.documents import Document
from models.domain_objects import IngestionJob
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from utilities.chunking_strategy_factory import ChunkingStrategyFactory
from utilities.constants import DOCX_FILE, PDF_FILE, RICH_TEXT_FILE, TEXT_FILE
from utilities.exceptions import RagUploadException

logger = logging.getLogger(__name__)
session = boto3.Session()
s3 = session.client("s3", region_name=os.environ["AWS_REGION"])


def _get_metadata(s3_uri: str, name: str) -> dict:
    return {"source": s3_uri, "name": name}


def _get_s3_uri(bucket: str, key: str) -> str:
    return f"s3://{bucket}/{key}"


def _extract_text_by_content_type(content_type: str, s3_object: dict) -> str:
    extraction_functions = {
        PDF_FILE: _extract_pdf_content,
        DOCX_FILE: _extract_docx_content,
        TEXT_FILE: _extract_text_content,
        RICH_TEXT_FILE: _extract_text_content,
    }

    extraction_function = extraction_functions.get(content_type)
    if extraction_function:
        return extraction_function(s3_object)
    else:
        logger.error(f"File has unsupported content type: {content_type}")
        raise RagUploadException("Unsupported file type")





def _extract_pdf_content(s3_object: dict) -> str:
    """Return text extracted from PDF.

    Extracts text content from a PDF file in an S3 object.

    Parameters
    ----------
    s3_object (dict): an S3 object containing a PDF file body

    Returns
    -------
    str: The extracted text from the PDF file.
    """
    file_content = s3_object["Body"].read()
    pdf_file = BytesIO(file_content)

    try:
        pdf_reader = PdfReader(pdf_file)
    except PdfReadError as e:
        logger.error(f"Error reading PDF file: {e}")
        raise

    return "".join(page.extract_text() or "" for page in pdf_reader.pages)


def _extract_docx_content(s3_object: dict) -> str:
    """Return text extracted from docx document.

    Extracts text content from a docx file in an S3 object.

    Parameters
    ----------
    s3_object (dict): an S3 object containing a docx file body

    Returns
    -------
    str: The extracted text from the docx file.
    """
    streaming_body = s3_object["Body"]
    file_as_bytes = streaming_body.read()
    bytes_as_file_like = BytesIO(file_as_bytes)

    doc = docx.Document(docx=bytes_as_file_like)

    output = "\n".join(para.text for para in doc.paragraphs)
    return output


def _extract_text_content(s3_object: dict) -> str:
    """
    Extracts text content from an S3 object. Decode as
    utf-8 to properly read special characters

    Parameters
    ----------
    s3_object (dict): an S3 object containing a text file body.
    """
    return s3_object["Body"].read().decode("utf-8", errors="replace")


def generate_chunks(ingestion_job: IngestionJob) -> list[Document]:
    """Generate chunks from an ingestion job using the configured chunking strategy.

    Parameters
    ----------
    ingestion_job : IngestionJob
        Ingestion job containing file information and chunking strategy

    Returns
    -------
    list[Document]
        List of document chunks for the processed file

    Raises
    ------
    RagUploadException
        If S3 path is invalid or file processing fails
    ValueError
        If chunking strategy is not supported
    """
    # Parse S3 URI using urlparse
    parsed_uri = urlparse(ingestion_job.s3_path)
    if not parsed_uri.netloc or not parsed_uri.path:
        logger.error(f"Invalid S3 path format: {ingestion_job.s3_path}")
        raise RagUploadException("Invalid S3 path format")

    bucket = parsed_uri.netloc
    key = parsed_uri.path.lstrip("/")

    content_type = key.split(".")[-1]
    try:
        s3_object = s3.get_object(Bucket=bucket, Key=key)
    except ClientError as e:
        logger.error(f"Error getting object from S3: {key}")
        raise e

    # Extract text and create initial document
    extracted_text = _extract_text_by_content_type(content_type=content_type, s3_object=s3_object)
    basename = os.path.basename(ingestion_job.s3_path)
    docs = [Document(page_content=extracted_text, metadata=_get_metadata(s3_uri=ingestion_job.s3_path, name=basename))]

    # Use factory to chunk documents based on strategy
    logger.info(f"Processing document with chunking strategy: {ingestion_job.chunk_strategy.type}")
    doc_chunks = ChunkingStrategyFactory.chunk_documents(docs, ingestion_job.chunk_strategy)

    # Update part number of doc metadata
    for i, doc in enumerate(doc_chunks):
        doc.metadata["part"] = i + 1

    logger.info(f"Generated {len(doc_chunks)} chunks for document: {basename}")
    return doc_chunks
