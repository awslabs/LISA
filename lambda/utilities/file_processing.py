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
import tempfile
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import boto3
from botocore.exceptions import ClientError
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import Docx2txtLoader, PyPDFLoader, TextLoader, UnstructuredMarkdownLoader
from langchain_core.documents import Document
from models.domain_objects import ChunkingStrategyType, IngestionJob
from utilities.constants import DOCX_FILE, MD_FILE, PDF_FILE, TEXT_FILE
from utilities.exceptions import RagUploadException

logger = logging.getLogger(__name__)
session = boto3.Session()
s3 = session.client("s3", region_name=os.environ["AWS_REGION"])


def _get_metadata(s3_uri: str, name: str) -> dict:
    return {"source": s3_uri, "name": name}


def _get_s3_uri(bucket: str, key: str) -> str:
    return f"s3://{bucket}/{key}"


def _gen_temp_file(s3_object: dict) -> str:
    """Download S3 object to a temp file and return path."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, dir="/tmp", suffix=".tmp")
    with open(temp_file.name, "wb") as f:
        f.write(s3_object["Body"].read())
    return temp_file.name


def _extract_text_by_content_type(content_type: str, s3_object: dict) -> List[Document]:
    extraction_functions = {
        PDF_FILE: _extract_pdf_content,
        DOCX_FILE: _extract_docx_content,
        TEXT_FILE: _extract_text_content,
        MD_FILE: _extract_md_content,
    }

    extraction_function = extraction_functions.get(content_type)
    if extraction_function:
        file_path = _gen_temp_file(s3_object)
        return extraction_function(file_path)
    else:
        logger.error(f"File has unsupported content type: {content_type}")
        raise RagUploadException("Unsupported file type")


def _generate_chunks(
    docs: List[Document], chunk_strategy: ChunkingStrategyType, chunk_size: Optional[int], chunk_overlap: Optional[int]
) -> List[Document]:
    if chunk_strategy == ChunkingStrategyType.FIXED:
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
    elif chunk_strategy == ChunkingStrategyType.HIERARCHICAL:

        def _join_related_elements(documents: List[Document]) -> List[Document]:
            """Join related elements based on hierarchy and category with optimized processing."""
            if not documents:
                return []

            joined_docs = []
            hierarchy_stack: List[Document] = []
            current_depth = -1

            def create_document_with_hierarchy(
                section: Document, content: List[Document], hierarchy: List[Document]
            ) -> Document:
                """Helper function to create document with full hierarchical context."""
                # Build content with full hierarchy
                hierarchy_content = [h.page_content for h in hierarchy]
                section_content = [section.page_content]
                content_parts = [d.page_content for d in content] if content else []

                full_content = "\n".join(hierarchy_content + section_content + content_parts)

                # Merge metadata from hierarchy
                merged_metadata = {}
                for h in hierarchy:
                    merged_metadata.update(h.metadata)
                merged_metadata.update(section.metadata)

                return Document(page_content=full_content, metadata=merged_metadata)

            def flush_section(depth: int, hierarchy_map: dict) -> None:
                """Helper function to process and flush sections at and below given depth."""
                for d in sorted(hierarchy_map.keys(), reverse=True):
                    if d >= depth:
                        section, content = hierarchy_map.pop(d)
                        # Get current hierarchy stack up to this depth
                        current_hierarchy = [h for h in hierarchy_stack if h.metadata.get("category_depth", 0) < d]
                        # Create document regardless of whether there's content
                        joined_docs.append(create_document_with_hierarchy(section, content, current_hierarchy))
                return None

            hierarchy_map: Dict[int, Tuple[Document, List[Document]]] = {}  # Store sections by depth

            for doc in documents:
                category = doc.metadata.get("category")
                depth = doc.metadata.get("category_depth", 0)

                if category == "Title":
                    # Flush any sections at or deeper than current depth
                    flush_section(depth, hierarchy_map)

                    # Update hierarchy stack
                    while hierarchy_stack and hierarchy_stack[-1].metadata.get("category_depth", 0) >= depth:
                        hierarchy_stack.pop()
                    hierarchy_stack.append(doc)

                    # Start new section
                    hierarchy_map[depth] = (doc, [])
                    current_depth = depth
                else:
                    if current_depth >= 0:
                        # Add to closest parent section
                        parent_depth = max((d for d in hierarchy_map.keys() if d <= current_depth), default=-1)
                        if parent_depth >= 0:
                            hierarchy_map[parent_depth][1].append(doc)
                    else:
                        # No active section, add as standalone with available hierarchy
                        if hierarchy_stack:
                            joined_docs.append(create_document_with_hierarchy(doc, [], hierarchy_stack))
                        else:
                            joined_docs.append(doc)

            # Flush remaining sections from deepest to shallowest
            flush_section(-1, hierarchy_map)

            return joined_docs

        # Split on headers
        supported_types = [
            "Title",
            # 'Image',
            "NarrativeText",
            "ListItem",
        ]
        filtered = [d for d in docs if d.metadata.get("category") in supported_types]

        return _join_related_elements(filtered)

    Extracts text content from a text file.

def _extract_pdf_content(file_path: str) -> List[Document]:
    """Return text extracted from PDF.

    Extracts text content from a PDF file.

    Parameters
    ----------
    file_path (str): path of the local PDF file

    Returns
    -------
    List[Document]: The extracted text from the pdf file.
    """
    loader = PyPDFLoader(
        file_path,
        extraction_mode="plain",
        mode="page",
    )
    return loader.load()  # type: ignore [no-any-return]


def _extract_docx_content(file_path: str) -> List[Document]:
    """Return text extracted from docx document.

    Extracts text content from a docx file.

    Parameters
    ----------
    file_path (str): path of the local docx file

    Returns
    -------
    List[Document]: The extracted text from the docx file.
    """
    loader = Docx2txtLoader(file_path)
    return loader.load()  # type: ignore [no-any-return]


def _extract_text_content(file_path: str) -> List[Document]:
    """Return text extracted from text document.

    Extracts text content from a text file.

    Parameters
    ----------
    file_path (str): path of the local text file

    Returns
    -------
    List[Document]: The extracted text from the text file.
    """
    loader = TextLoader(file_path=file_path, encoding="utf-8")
    return loader.load()  # type: ignore [no-any-return]


def _extract_md_content(file_path: str) -> List[Document]:
    """Return text extracted from md document.

    Extracts text content from a md file.

    Parameters
    ----------
    file_path (str): path of the local md file

    Returns
    -------
    List[Document]: The extracted text from the md file.
    """
    import nltk

    nltk.data.path.append(os.path.join(os.environ["LAMBDA_TASK_ROOT"], "nltk_data"))

    loader = UnstructuredMarkdownLoader(
        file_path=file_path,
        mode="elements",
    )
    return loader.load()  # type: ignore [no-any-return]


def generate_chunks(ingestion_job: IngestionJob) -> list[Document]:
    """Generate chunks from an ingestion job.

    Parameters
    ----------
    ingestion_job (IngestionJob): Ingestion job containing file information and chunking strategy

    Returns
    -------
    List[Document]: List of document chunks for the processed file
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

    chunk_strategy = ingestion_job.chunk_strategy
    if chunk_strategy.type == ChunkingStrategyType.FIXED:
        return generate_fixed_chunks(ingestion_job, content_type, s3_object)
    elif chunk_strategy.type == ChunkingStrategyType.HIERARCHICAL:
        if content_type != MD_FILE:
            logger.error("Hierarchical chunking only supports markdown files.")
            raise RagUploadException("Hierarchical chunking only supports markdown files.")
        return generate_hierarchical_chunks(ingestion_job, content_type, s3_object)

    logger.error(f"Unrecognized chunk strategy {chunk_strategy.type}")
    raise Exception("Unrecognized chunk strategy")


def generate_fixed_chunks(ingestion_job: IngestionJob, content_type: str, s3_object: Any) -> list[Document]:
    # Get chunk parameters from chunking strategy
    chunk_size = ingestion_job.chunk_strategy.size if ingestion_job.chunk_strategy.size else None
    chunk_overlap = ingestion_job.chunk_strategy.overlap if ingestion_job.chunk_strategy.overlap else None

    # Extract text into documents and update document metadata
    docs = _extract_text_by_content_type(content_type=content_type, s3_object=s3_object)
    basename = os.path.basename(ingestion_job.s3_path)
    for d in docs:
        d.metadata.update(**_get_metadata(s3_uri=ingestion_job.s3_path, name=basename))

    # Generate chunks using existing helper function
    doc_chunks = _generate_chunks(
        docs, chunk_strategy=ingestion_job.chunk_strategy.type, chunk_size=chunk_size, chunk_overlap=chunk_overlap
    )

    # Update part number of doc metadata
    for i, doc in enumerate(doc_chunks):
        doc.metadata["part"] = i + 1

    return doc_chunks


def generate_hierarchical_chunks(ingestion_job: IngestionJob, content_type: str, s3_object: dict) -> list[Document]:
    # Extract text into documents and update document metadata
    docs = _extract_text_by_content_type(content_type=content_type, s3_object=s3_object)
    basename = os.path.basename(ingestion_job.s3_path)
    for d in docs:
        d.metadata.update(**_get_metadata(s3_uri=ingestion_job.s3_path, name=basename))

    # Generate chunks using existing helper function
    doc_chunks = _generate_chunks(
        docs, chunk_strategy=ingestion_job.chunk_strategy.type, chunk_size=None, chunk_overlap=None
    )

    # Update part number of doc metadata
    for i, doc in enumerate(doc_chunks):
        doc.metadata["part"] = i + 1

    return doc_chunks
