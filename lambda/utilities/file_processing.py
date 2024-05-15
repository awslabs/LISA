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
from typing import List, Optional

import boto3
import docx
from botocore.exceptions import ClientError
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError
from utilities.constants import DOCX_FILE, PDF_FILE, TEXT_FILE
from utilities.exceptions import RagUploadException

logger = logging.getLogger(__name__)
session = boto3.Session()
s3 = session.client("s3")


def _get_metadata(s3_uri: str) -> dict:
    return {"source": s3_uri}


def _get_s3_uri(bucket: str, key: str) -> str:
    return f"s3://{bucket}/{key}"


def _extract_text_by_content_type(content_type: str, s3_object: dict) -> str:
    extraction_functions = {
        PDF_FILE: _extract_pdf_content,
        DOCX_FILE: _extract_docx_content,
        TEXT_FILE: lambda obj: obj["Body"].read(),
    }

    extraction_function = extraction_functions.get(content_type)
    if extraction_function:
        return str(extraction_function(s3_object))
    else:
        logger.error(f"File has unsupported content type: {content_type}")
        raise RagUploadException("Unsupported file type")


def _generate_chunks(docs: List[Document], chunk_size: Optional[int], chunk_overlap: Optional[int]) -> List[Document]:
    if not chunk_size:
        chunk_size = int(os.getenv("CHUNK_SIZE", "512"))
    if not chunk_overlap:
        chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "51"))

    if chunk_size < 100 or chunk_size > 10000:
        raise RagUploadException("Invalid chunk size")

    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise RagUploadException("Invalid chunk overlap")

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
    )
    return text_splitter.split_documents(docs)  # type: ignore [no-any-return]


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


def process_record(s3_keys: List[str], chunk_size: Optional[int], chunk_overlap: Optional[int]) -> List[List[Document]]:
    """Process a single file from S3.

    Parameters
    ----------
    record (dict): The S3 record to process.

    """
    bucket = os.environ["BUCKET_NAME"]
    chunks = []
    for key in s3_keys:
        content_type = key.split(".")[-1]
        try:
            s3_object = s3.get_object(Bucket=bucket, Key=key)
        except ClientError as e:
            logger.error(f"Error getting object from S3: {key}")
            raise e
        s3_uri = _get_s3_uri(bucket=bucket, key=key)
        extracted_text = _extract_text_by_content_type(content_type=content_type, s3_object=s3_object)
        docs = [Document(page_content=extracted_text, metadata=_get_metadata(s3_uri=s3_uri))]
        chunks.append(_generate_chunks(docs, chunk_size=chunk_size, chunk_overlap=chunk_overlap))

    return chunks
