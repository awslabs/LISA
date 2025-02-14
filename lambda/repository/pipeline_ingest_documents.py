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

"""Lambda function for pipeline document ingestion."""

import logging
import os
from typing import Any, Dict, List

import boto3
from repository.lambda_functions import RagDocumentRepository
from utilities.common_functions import get_username, retry_config
from utilities.file_processing import process_record
from utilities.validation import validate_chunk_params, validate_model_name, ValidationError
from utilities.vector_store import get_vector_store_client

from .lambda_functions import ChunkStrategyType, get_embeddings_pipeline, IngestionType, RagDocument

logger = logging.getLogger(__name__)
session = boto3.Session()
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)
doc_repo = RagDocumentRepository(os.environ["RAG_DOCUMENT_TABLE"], os.environ["RAG_SUB_DOCUMENT_TABLE"])


def handle_pipeline_ingest_documents(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handle pipeline document ingestion."""
    try:
        # Extract and validate inputs
        bucket, key, repository_id, pipeline_config = validate_event(event)
        chunk_size, chunk_overlap, embedding_model = extract_and_validate_config(pipeline_config)

        logger.info(f"Processing document s3://{bucket}/{key} for repository {repository_id}")

        # Process document
        docs = process_document(bucket, key, chunk_size, chunk_overlap)

        # Prepare chunks
        texts, metadatas = prepare_chunks(docs, repository_id)

        # Store in vector store
        all_ids = store_chunks_in_vectorstore(texts, metadatas, repository_id, embedding_model)

        # Create RAG document
        username = get_username(event)
        create_rag_document(repository_id, embedding_model, key, docs, all_ids, chunk_size, chunk_overlap, username)

        return {
            "message": f"Successfully processed document s3://{bucket}/{key}",
            "repository_id": repository_id,
            "chunks_processed": len(all_ids),
            "document_ids": all_ids,
        }

    except ValidationError as e:
        error_msg = f"Validation error: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"Failed to process document: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise Exception(error_msg)


def batch_texts(texts: List[str], metadatas: List[Dict], batch_size: int = 500) -> list[tuple[list[str], list[dict]]]:
    """
    Split texts and metadata into batches of specified size.

    Args:
        texts: List of text strings to batch
        metadatas: List of metadata dictionaries
        batch_size: Maximum size of each batch
    Returns:
        List of tuples containing (texts_batch, metadatas_batch)
    """
    batches = []
    for i in range(0, len(texts), batch_size):
        text_batch = texts[i : i + batch_size]
        metadata_batch = metadatas[i : i + batch_size]
        batches.append((text_batch, metadata_batch))
    return batches


def validate_event(event: Dict[str, Any]) -> tuple[str, str, str, Dict]:
    """Validate and extract required fields from the event."""
    if "bucket" not in event or "key" not in event:
        raise ValidationError("Missing required fields: bucket and key")

    bucket = event["bucket"]
    key = event["key"]
    repository_id = event["repositoryId"]
    pipeline_config = event["pipelineConfig"]

    return bucket, key, repository_id, pipeline_config


def extract_and_validate_config(pipeline_config: Dict) -> tuple[int, int, str]:
    """Extract and validate configuration parameters."""
    chunk_size = int(pipeline_config["chunkSize"])
    chunk_overlap = int(pipeline_config["chunkOverlap"])
    embedding_model = pipeline_config["embeddingModel"]

    validate_model_name(embedding_model)
    validate_chunk_params(chunk_size, chunk_overlap)

    return chunk_size, chunk_overlap, embedding_model


def process_document(bucket: str, key: str, chunk_size: int, chunk_overlap: int) -> List:
    """Process the document and return chunks."""
    docs: list = process_record(
        s3_keys=[key],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        bucket=bucket,
    )

    if not docs or not docs[0]:
        raise ValidationError(f"No content extracted from document s3://{bucket}/{key}")

    return docs


def prepare_chunks(docs: List, repository_id: str) -> tuple[List[str], List[Dict]]:
    """Prepare texts and metadata from document chunks."""
    texts = []
    metadatas = []

    for doc_list in docs:
        for doc in doc_list:
            texts.append(doc.page_content)
            doc.metadata["repository_id"] = repository_id
            metadatas.append(doc.metadata)

    return texts, metadatas


def store_chunks_in_vectorstore(
    texts: List[str], metadatas: List[Dict], repository_id: str, embedding_model: str
) -> List[str]:
    """Store document chunks in vector store."""
    embeddings = get_embeddings_pipeline(model_name=embedding_model)
    vs = get_vector_store_client(
        repository_id,
        index=embedding_model,
        embeddings=embeddings,
    )

    all_ids = []
    batches = batch_texts(texts, metadatas)
    total_batches = len(batches)

    logger.info(f"Processing {len(texts)} texts in {total_batches} batches")

    for i, (text_batch, metadata_batch) in enumerate(batches, 1):
        logger.info(f"Processing batch {i}/{total_batches} with {len(text_batch)} texts")
        batch_ids = vs.add_texts(texts=text_batch, metadatas=metadata_batch)
        if not batch_ids:
            raise Exception(f"Failed to store documents in vector store for batch {i}")
        all_ids.extend(batch_ids)
        logger.info(f"Successfully processed batch {i}")

    if not all_ids:
        raise Exception("Failed to store any documents in vector store")

    return all_ids


def create_rag_document(
    repository_id: str,
    embedding_model: str,
    key: str,
    docs: List,
    all_ids: List[str],
    chunk_size: int,
    chunk_overlap: int,
    username: str,
) -> None:
    """Create and save RAG document entry."""
    doc_entity = RagDocument(
        repository_id=repository_id,
        collection_id=embedding_model,
        document_name=key,
        source=docs[0][0].metadata.get("source"),
        subdocs=all_ids,
        chunk_strategy={
            "type": ChunkStrategyType.FIXED.value,
            "size": str(chunk_size),
            "overlap": str(chunk_overlap),
        },
        username=username,
        ingestion_type=IngestionType.AUTO,
    )
    doc_repo.save(doc_entity)
