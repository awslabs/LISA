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
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import boto3
from models.domain_objects import (
    ChunkingStrategy,
    FixedChunkingStrategy,
    IngestionJob,
    IngestionStatus,
    IngestionType,
    RagDocument,
)
from repository.collection_service import CollectionService
from repository.embeddings import RagEmbeddings
from repository.ingestion_job_repo import IngestionJobRepository
from repository.ingestion_service import DocumentIngestionService
from repository.rag_document_repo import RagDocumentRepository
from repository.vector_store_repo import VectorStoreRepository
from utilities.auth import get_username
from utilities.bedrock_kb import ingest_document_to_kb
from utilities.common_functions import retry_config
from utilities.file_processing import generate_chunks
from utilities.repository_types import RepositoryType
from utilities.vector_store import get_vector_store_client

dynamodb = boto3.resource("dynamodb", region_name=os.environ["AWS_REGION"], config=retry_config)
ingestion_job_table = dynamodb.Table(os.environ["LISA_INGESTION_JOB_TABLE_NAME"])
ingestion_service = DocumentIngestionService()
ingestion_job_repository = IngestionJobRepository()
vs_repo = VectorStoreRepository()
rag_document_repository = RagDocumentRepository(os.environ["RAG_DOCUMENT_TABLE"], os.environ["RAG_SUB_DOCUMENT_TABLE"])
collection_service = CollectionService(vector_store_repo=vs_repo, document_repo=rag_document_repository)

logger = logging.getLogger(__name__)
session = boto3.Session()
s3 = boto3.client("s3", region_name=os.environ["AWS_REGION"], config=retry_config)
bedrock_agent = boto3.client("bedrock-agent", region_name=os.environ["AWS_REGION"], config=retry_config)
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)


def pipeline_ingest(job: IngestionJob) -> None:
    texts: list[str] = []
    metadatas: list[dict] = []
    all_ids: list[str] = []
    try:
        # chunk and save chunks in vector store
        repository = vs_repo.find_repository_by_id(job.repository_id)
        if RepositoryType.is_type(repository, RepositoryType.BEDROCK_KB):
            ingest_document_to_kb(
                s3_client=s3,
                bedrock_agent_client=bedrock_agent,
                job=job,
                repository=repository,
            )
        else:
            documents = generate_chunks(job)
            texts, metadatas = prepare_chunks(documents, job.repository_id, job.collection_id)
            all_ids = store_chunks_in_vectorstore(
                texts=texts,
                metadatas=metadatas,
                repository_id=job.repository_id,
                collection_id=job.collection_id,
                embedding_model=job.embedding_model,
            )

        # remove old
        for rag_document in rag_document_repository.find_by_source(
            job.repository_id, job.collection_id, job.s3_path, join_docs=True
        ):
            prev_job = ingestion_job_repository.find_by_document(rag_document.document_id)

            if prev_job:
                ingestion_job_repository.update_status(prev_job, IngestionStatus.DELETE_IN_PROGRESS)
            if not RepositoryType.is_type(repository, RepositoryType.BEDROCK_KB):
                remove_document_from_vectorstore(rag_document)
            rag_document_repository.delete_by_id(rag_document.document_id)

            if prev_job:
                ingestion_job_repository.update_status(prev_job, IngestionStatus.DELETE_COMPLETED)

        ingestion_type = IngestionType.AUTO
        if job.username != "system":
            ingestion_type = IngestionType.MANUAL

        # save to dynamodb
        rag_document = RagDocument(
            repository_id=job.repository_id,
            collection_id=job.collection_id,
            document_name=os.path.basename(job.s3_path),
            source=job.s3_path,
            subdocs=all_ids,
            chunk_strategy=job.chunk_strategy,
            username=job.username,
            ingestion_type=ingestion_type,
        )
        rag_document_repository.save(rag_document)

        # update IngstionJob
        job.status = IngestionStatus.INGESTION_COMPLETED
        job.document_id = rag_document.document_id
        ingestion_job_repository.save(job)

        logging.info(f"Successfully ingested document {job.s3_path} ({len(all_ids)} chunks) into {job.collection_id}")
    except Exception as e:
        ingestion_job_repository.update_status(job, IngestionStatus.INGESTION_FAILED)
        error_msg = f"Failed to process document: {str(e)}"
        logger.error(error_msg, exc_info=True)
        logger.error(f"Job: {job.model_dump_json(indent=2)}")
        raise Exception(error_msg)


def remove_document_from_vectorstore(doc: RagDocument) -> None:
    # Delete from the Vector Store
    embeddings = RagEmbeddings(model_name=doc.collection_id)
    vector_store = get_vector_store_client(
        doc.repository_id,
        collection_id=doc.collection_id,
        embeddings=embeddings,
    )
    vector_store.delete(doc.subdocs)


def handle_pipeline_ingest_event(event: Dict[str, Any], context: Any) -> None:
    """Handle pipeline document ingestion."""
    # Extract and validate inputs
    logger.debug(f"Received event: {event}")

    detail = event.get("detail", {})
    bucket = detail.get("bucket", None)
    username = get_username(event)
    key = detail.get("key", None)
    repository_id = detail.get("repositoryId", None)
    pipeline_config = detail.get("pipelineConfig", None)
    collection_id = pipeline_config.get("collectionId", None)
    s3_path = f"s3://{bucket}/{key}"
    embedding_model = pipeline_config.get("embeddingModel", None)
    if collection_id:
        collection = collection_service.get_collection(
            collection_id=collection_id, repository_id=repository_id, is_admin=True, username="", user_groups=[]
        )
        embedding_model = collection.embeddingModel
    else:
        collection_id = embedding_model
    logger.info(f"Ingesting object {s3_path} for repository {repository_id}/{embedding_model}")

    chunk_strategy = extract_chunk_strategy(pipeline_config)

    # Get repository and metadata
    repository = vs_repo.find_repository_by_id(repository_id)
    metadata = collection_service.get_collection_metadata(repository, None)

    # create ingestion job and save it to dynamodb
    job = IngestionJob(
        repository_id=repository_id,
        collection_id=collection_id,
        embedding_model=embedding_model,
        chunk_strategy=chunk_strategy,
        s3_path=s3_path,
        username=username,
        ingestion_type=IngestionType.MANUAL,
        metadata=metadata,
    )
    ingestion_job_repository.save(job)
    ingestion_service.submit_create_job(job)

    logger.info(f"Ingesting document {s3_path} for repository {repository_id}")


def handle_pipline_ingest_schedule(event: Dict[str, Any], context: Any) -> None:
    """
    Lists all objects in the specified S3 bucket and prefix that were modified in the last 24 hours.

    Args:
        event: Event data containing bucket and prefix information
        context: Lambda context

    Returns:
        Dictionary containing array of files with their bucket and key
    """
    # Log the full event for debugging
    logger.debug(f"Received event: {event}")

    detail = event.get("detail", {})
    bucket = detail.get("bucket", None)
    username = get_username(event)
    prefix = detail.get("prefix", None)
    repository_id = detail.get("repositoryId", None)
    pipeline_config = detail.get("pipelineConfig", None)
    embedding_model = pipeline_config.get("embeddingModel", None)

    # hard code fixed length chunking until more strategies are implemented
    chunk_strategy = extract_chunk_strategy(pipeline_config)

    try:
        # Add debug logging
        logger.info(f"Processing request for bucket: {bucket}, prefix: {prefix}")

        # Calculate timestamp for 24 hours ago
        twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)

        # List to store matching objects
        modified_keys = []

        # Use paginator to handle case where there are more than 1000 objects
        paginator = s3.get_paginator("list_objects_v2")

        # Add debug logging for S3 list operation
        logger.info(f"Listing objects in {bucket}{prefix} modified after {twenty_four_hours_ago}")

        # Iterate through all objects in the bucket/prefix
        try:
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                if "Contents" not in page:
                    logger.info(f"No contents found in page for {bucket}{prefix}")
                    continue

                # Check each object's last modified time
                for obj in page["Contents"]:
                    last_modified = obj["LastModified"]
                    if last_modified >= twenty_four_hours_ago:
                        logger.info(f"Found modified file: {obj['Key']} (Last Modified: {last_modified})")
                        modified_keys.append(obj["Key"])
                    else:
                        logger.debug(
                            f"Skipping file {obj['Key']} - Last modified {last_modified} before cutoff "
                            f"{twenty_four_hours_ago}"
                        )
        except Exception as e:
            logger.error(f"Error during S3 list operation: {str(e)}", exc_info=True)
            raise

        # Get repository and metadata
        repository = vs_repo.find_repository_by_id(repository_id)
        metadata = collection_service.get_collection_metadata(repository, None)

        # create an IngestionJob for every object created/modified
        for key in modified_keys:
            job = IngestionJob(
                repository_id=repository_id,
                collection_id=embedding_model,
                chunk_strategy=chunk_strategy,
                s3_path=f"s3://{bucket}/{key}",
                username=username,
                ingestion_type=IngestionType.AUTO,
                metadata=metadata,
            )
            ingestion_job_repository.save(job)
            ingestion_service.submit_create_job(job)

        logger.info(f"Found {len(modified_keys)} modified files in {bucket}{prefix}")
    except Exception as e:
        logger.error(f"Error listing objects: {str(e)}", exc_info=True)
        raise e


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


def extract_chunk_strategy(pipeline_config: Dict) -> ChunkingStrategy:
    """
    Extract and validate chunking strategy from pipeline configuration.

    Supports both new chunkingStrategy object format and legacy flat fields for backward compatibility.
    Uses Pydantic model validation to ensure data integrity.

    Args:
        pipeline_config: Pipeline configuration dictionary

    Returns:
        ChunkingStrategy object (validated Pydantic model)

    Raises:
        ValueError: If chunking strategy type is unsupported or validation fails
    """
    # Check for new chunkingStrategy object format first
    if "chunkingStrategy" in pipeline_config and pipeline_config["chunkingStrategy"]:
        chunking_strategy = pipeline_config["chunkingStrategy"]
        chunk_type = chunking_strategy.get("type", "fixed")

        if chunk_type == "fixed":
            # Use Pydantic model validation for type safety and validation
            return FixedChunkingStrategy.model_validate(chunking_strategy)
        else:
            # Future: Handle other chunking strategy types (semantic, recursive, etc.)
            raise ValueError(f"Unsupported chunking strategy type: {chunk_type}")

    # Fall back to legacy flat fields for backward compatibility
    elif "chunkSize" in pipeline_config and "chunkOverlap" in pipeline_config:
        chunk_size = int(pipeline_config["chunkSize"])
        chunk_overlap = int(pipeline_config["chunkOverlap"])
        # Use Pydantic model for validation
        return FixedChunkingStrategy(size=chunk_size, overlap=chunk_overlap)

    # Default values if neither format is present
    else:
        logger.warning("No chunking strategy found in pipeline config, using defaults")
        return FixedChunkingStrategy(size=512, overlap=51)


def prepare_chunks(docs: List, repository_id: str, collection_id: str) -> tuple[List[str], List[Dict]]:
    """Prepare texts and metadata from document chunks."""
    texts = []
    metadatas = []

    for doc in docs:
        texts.append(doc.page_content)
        doc.metadata["repository_id"] = repository_id
        doc.metadata["collection_id"] = collection_id
        metadatas.append(doc.metadata)

    return texts, metadatas


def store_chunks_in_vectorstore(
    texts: List[str], metadatas: List[Dict], repository_id: str, collection_id: str, embedding_model: str
) -> List[str]:
    """Store document chunks in vector store."""
    embeddings = RagEmbeddings(model_name=embedding_model)
    vs = get_vector_store_client(
        repository_id,
        collection_id,
        embeddings,
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
