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

"""Batch container processing functions for pipeline document ingestion."""

import logging
import os

import boto3
from models.domain_objects import (
    IngestionJob,
    IngestionStatus,
    IngestionType,
    JobActionType,
    NoneChunkingStrategy,
    RagDocument,
)
from repository.collection_service import CollectionService
from repository.embeddings import RagEmbeddings
from repository.ingestion_job_repo import IngestionJobRepository
from repository.ingestion_service import DocumentIngestionService
from repository.metadata_generator import MetadataGenerator
from repository.rag_document_repo import RagDocumentRepository
from repository.s3_metadata_manager import S3MetadataManager
from repository.services.repository_service_factory import RepositoryServiceFactory
from repository.vector_store_repo import VectorStoreRepository
from utilities.bedrock_kb import get_datasource_bucket_for_collection, ingest_document_to_kb, S3DocumentDiscoveryService
from utilities.common_functions import retry_config
from utilities.file_processing import generate_chunks
from utilities.repository_types import RepositoryType
from utilities.time import now

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


def pipeline_ingest(job: IngestionJob) -> None:
    """
    Ingest a single document or batch of documents.

    Routes to appropriate handler based on job type.
    """
    if job.job_type == JobActionType.DOCUMENT_BATCH_INGESTION:
        pipeline_ingest_documents(job)
    else:
        pipeline_ingest_document(job)


def pipeline_ingest_document(job: IngestionJob) -> None:
    """Ingest a single document."""
    texts: list[str] = []
    metadatas: list[dict] = []
    all_ids: list[str] = []
    try:
        # chunk and save chunks in vector store
        repository = vs_repo.find_repository_by_id(job.repository_id)
        if RepositoryType.is_type(repository, RepositoryType.BEDROCK_KB):
            # Bedrock KB path: Copy document to KB bucket and track
            # Get KB bucket for this collection (supports multiple config formats)
            try:
                kb_bucket = get_datasource_bucket_for_collection(
                    repository=repository,
                    collection_id=job.collection_id,  # type: ignore[arg-type]
                )
            except ValueError as e:
                error_msg = str(e)
                logger.error(error_msg)
                job.status = IngestionStatus.INGESTION_FAILED
                job.error_message = error_msg
                ingestion_job_repository.save(job)
                raise

            # Determine if document needs to be copied to KB bucket
            source_bucket = job.s3_path.split("/")[2]
            needs_copy = source_bucket != kb_bucket

            # Set canonical KB path
            kb_s3_path = f"s3://{kb_bucket}/{os.path.basename(job.s3_path)}"

            if needs_copy:
                # Document uploaded to LISA bucket, needs to be copied to KB bucket
                logger.info(
                    f"Document {job.s3_path} uploaded to LISA bucket. " f"Copying to KB data source bucket {kb_bucket}"
                )

            # Check if document already exists (idempotent operation)
            existing_docs = list(
                rag_document_repository.find_by_source(
                    job.repository_id, job.collection_id, kb_s3_path, join_docs=False  # type: ignore[arg-type]
                )
            )

            if existing_docs and not needs_copy:
                # Document already tracked and in KB bucket, update upload_date and return
                existing_doc = existing_docs[0]
                existing_doc.upload_date = now()
                rag_document_repository.save(existing_doc)

                job.status = IngestionStatus.INGESTION_COMPLETED
                job.document_id = existing_doc.document_id
                ingestion_job_repository.save(job)
                logger.info(f"Document {kb_s3_path} already tracked, updated upload_date")
                return

            # Copy document to KB bucket if needed (user upload via LISA)
            if needs_copy:
                try:
                    # This will copy file to KB bucket, delete from source, and trigger KB ingestion
                    ingest_document_to_kb(
                        s3_client=s3,
                        bedrock_agent_client=bedrock_agent,
                        job=job,
                        repository=repository,
                    )
                    logger.info(f"Copied document from {job.s3_path} to {kb_s3_path}")
                except Exception as e:
                    logger.error(f"Failed to copy document to KB bucket: {e}")
                    raise

            rag_document = RagDocument(
                repository_id=job.repository_id,
                collection_id=job.collection_id,
                document_name=os.path.basename(kb_s3_path),
                source=kb_s3_path,  # Use KB bucket path as canonical source
                subdocs=[],  # Empty - KB manages chunks internally
                chunk_strategy=NoneChunkingStrategy(),  # KB manages chunking
                username=job.username,
                ingestion_type=job.ingestion_type,
            )
            rag_document_repository.save(rag_document)

            # Generate and upload metadata.json file for Bedrock KB
            try:
                metadata_generator = MetadataGenerator()
                s3_metadata_manager = S3MetadataManager()

                # Get collection for metadata
                collection = None
                try:
                    collection = collection_service.get_collection(
                        collection_id=job.collection_id,  # type: ignore[arg-type]
                        repository_id=job.repository_id,
                        username="system",
                        user_groups=[],
                        is_admin=True,
                    )
                except Exception as e:
                    logger.warning(f"Could not fetch collection for metadata: {e}")

                # Generate metadata content
                metadata_content = metadata_generator.generate_metadata_json(
                    repository=repository, collection=collection, document_metadata=job.metadata
                )

                # Extract bucket and key from S3 path
                bucket_name = kb_s3_path.split("/")[2]
                document_key = "/".join(kb_s3_path.split("/")[3:])

                # Upload metadata file
                s3_metadata_manager.upload_metadata_file(
                    s3_client=s3, bucket=bucket_name, document_key=document_key, metadata_content=metadata_content
                )
                logger.info(f"Created metadata file for {kb_s3_path}")
            except Exception as e:
                logger.error(f"Failed to create metadata file for {kb_s3_path}: {e}")
                # Continue with ingestion even if metadata fails

            job.status = IngestionStatus.INGESTION_COMPLETED
            job.document_id = rag_document.document_id
            ingestion_job_repository.save(job)
            logger.info(
                f"Tracked document {kb_s3_path} for Bedrock KB repository {job.repository_id}. "
                f"KB will handle ingestion automatically."
            )
            return  # Early return for Bedrock KB path

        # Non-Bedrock KB path
        documents = generate_chunks(job)
        if not job.collection_id and job.metadata:
            job.collection_id = job.metadata.get("collectionId")
        texts, metadatas = prepare_chunks(documents, job.repository_id, job.collection_id)  # type: ignore[arg-type]
        all_ids = store_chunks_in_vectorstore(
            texts=texts,
            metadatas=metadatas,
            repository_id=job.repository_id,
            collection_id=job.collection_id,  # type: ignore[arg-type]
            embedding_model=job.embedding_model,  # type: ignore[arg-type]
        )

        # remove old
        for rag_document in list(
            rag_document_repository.find_by_source(
                job.repository_id,
                job.collection_id,  # type: ignore[arg-type]
                job.s3_path,
                join_docs=True,
            )
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


def pipeline_ingest_documents(job: IngestionJob) -> None:
    """
    Ingest multiple documents in batch (up to 100 at a time).

    Processes documents from s3_paths field containing list of S3 paths.
    If s3_paths is empty, triggers S3 bucket scan to discover existing documents.
    """
    try:
        logger.info(f"Starting batch ingestion for job {job.id}")

        # Check if this is an S3 discovery scan job (empty s3_paths)
        if not job.s3_paths:
            # Handle S3 bucket scanning for existing documents
            _handle_s3_discovery_scan(job)
            return

        # Normal batch ingestion path
        # Extract document list from s3_paths field

        document_paths = job.s3_paths
        if not isinstance(document_paths, list):
            raise ValueError("'s3_paths' must be a list")

        if len(document_paths) > 100:
            raise ValueError(f"Batch size {len(document_paths)} exceeds maximum of 100 documents")

        logger.info(f"Processing {len(document_paths)} documents in batch")

        # Update job status
        ingestion_job_repository.update_status(job, IngestionStatus.INGESTION_IN_PROGRESS)

        # Process each document and collect document IDs
        successful = 0
        failed = 0
        errors = []
        document_ids = []

        for s3_path in document_paths:
            try:
                # Create individual job for each document
                doc_job = IngestionJob(
                    repository_id=job.repository_id,
                    collection_id=job.collection_id,
                    embedding_model=job.embedding_model,
                    chunk_strategy=job.chunk_strategy,
                    s3_path=s3_path,
                    username=job.username,
                    metadata=job.metadata,
                    ingestion_type=job.ingestion_type,
                    job_type=JobActionType.DOCUMENT_INGESTION,
                )

                # Process the document
                pipeline_ingest_document(doc_job)
                successful += 1
                document_ids.append(doc_job.document_id)
                logger.info(f"Successfully ingested document {s3_path}")

            except Exception as e:
                failed += 1
                error_msg = f"Failed to ingest {s3_path}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)

        # Update job with document IDs
        job.document_ids = document_ids  # type: ignore[assignment]

        if failed == 0:
            ingestion_job_repository.update_status(job, IngestionStatus.INGESTION_COMPLETED)
            logger.info(f"Batch ingestion completed: {successful} successful, {failed} failed")
        else:
            ingestion_job_repository.update_status(job, IngestionStatus.INGESTION_FAILED)
            logger.warning(f"Batch ingestion completed with errors: {successful} successful, {failed} failed")

    except Exception as e:
        ingestion_job_repository.update_status(job, IngestionStatus.INGESTION_FAILED)
        error_msg = f"Failed to process batch ingestion: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise Exception(error_msg)


def _handle_s3_discovery_scan(job: IngestionJob) -> None:
    """
    Handle S3 bucket scanning for existing documents.

    Delegates to S3DocumentDiscoveryService for the actual work.

    Args:
        job: Batch ingestion job with empty s3_paths (signals scan mode)
    """
    try:
        logger.info(f"Starting S3 discovery scan for job {job.id}")

        # Extract bucket and prefix from s3_path field
        # Format: s3://bucket/prefix or s3://bucket/
        if not job.s3_path or not job.s3_path.startswith("s3://"):
            raise ValueError("S3 scan job missing valid 's3_path' field")

        # Parse s3://bucket/prefix
        path_parts = job.s3_path.replace("s3://", "").split("/", 1)
        s3_bucket = path_parts[0]
        s3_prefix = path_parts[1] if len(path_parts) > 1 else ""

        # Remove trailing slash from prefix if present
        if s3_prefix.endswith("/"):
            s3_prefix = s3_prefix[:-1]

        # Update job status
        ingestion_job_repository.update_status(job, IngestionStatus.INGESTION_IN_PROGRESS)

        # Initialize discovery service
        metadata_generator = MetadataGenerator()
        s3_metadata_manager = S3MetadataManager()

        discovery_service = S3DocumentDiscoveryService(
            s3_client=s3,
            bedrock_agent_client=bedrock_agent,
            rag_document_repository=rag_document_repository,
            metadata_generator=metadata_generator,
            s3_metadata_manager=s3_metadata_manager,
            collection_service=collection_service,
            vector_store_repo=vs_repo,
        )

        # Perform discovery and ingestion
        result = discovery_service.discover_and_ingest_documents(
            repository_id=job.repository_id,
            collection_id=job.collection_id,  # type: ignore[arg-type]
            s3_bucket=s3_bucket,
            s3_prefix=s3_prefix,
            ingestion_type=job.ingestion_type,
        )

        # Update job with results
        job.document_ids = result.document_ids

        if result.failed == 0:
            ingestion_job_repository.update_status(job, IngestionStatus.INGESTION_COMPLETED)
        else:
            ingestion_job_repository.update_status(job, IngestionStatus.INGESTION_FAILED)

    except Exception as e:
        ingestion_job_repository.update_status(job, IngestionStatus.INGESTION_FAILED)
        error_msg = f"Failed to process S3 discovery scan: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise Exception(error_msg)


def remove_document_from_vectorstore(doc: RagDocument) -> None:
    """Delete document from vector store using repository service."""
    vs_repo = VectorStoreRepository()
    repository = vs_repo.find_repository_by_id(doc.repository_id)

    service = RepositoryServiceFactory.create_service(repository)
    embeddings = RagEmbeddings(model_name=doc.collection_id)
    vector_store = service.get_vector_store_client(
        collection_id=doc.collection_id,
        embeddings=embeddings,
    )
    vector_store.delete(doc.subdocs)  # type: ignore[union-attr]


def batch_texts(texts: list[str], metadatas: list[dict], batch_size: int = 256) -> list[tuple[list[str], list[dict]]]:
    batches = []
    for i in range(0, len(texts), batch_size):
        batches.append((texts[i : i + batch_size], metadatas[i : i + batch_size]))
    return batches


def prepare_chunks(docs: list, repository_id: str, collection_id: str) -> tuple[list[str], list[dict]]:
    """Prepare texts and metadata from document chunks."""
    texts = []
    metadatas = []

    for doc in docs:
        texts.append(doc.page_content)
        metadatas.append(doc.metadata)

    return texts, metadatas


def store_chunks_in_vectorstore(
    texts: list[str], metadatas: list[dict], repository_id: str, collection_id: str, embedding_model: str
) -> list[str]:
    """Store document chunks in vector store using repository service."""
    vs_repo = VectorStoreRepository()
    repository = vs_repo.find_repository_by_id(repository_id)

    service = RepositoryServiceFactory.create_service(repository)
    embeddings = RagEmbeddings(model_name=embedding_model)
    vs = service.get_vector_store_client(
        collection_id=collection_id,
        embeddings=embeddings,
    )

    all_ids = []
    batches = batch_texts(texts, metadatas)
    total_batches = len(batches)

    logger.info(f"Processing {len(texts)} texts in {total_batches} batches")

    for i, (text_batch, metadata_batch) in enumerate(batches, 1):
        logger.info(f"Processing batch {i}/{total_batches} with {len(text_batch)} texts")
        batch_ids = vs.add_texts(texts=text_batch, metadatas=metadata_batch)  # type: ignore[union-attr]
        if not batch_ids:
            raise Exception(f"Failed to store documents in vector store for batch {i}")
        all_ids.extend(batch_ids)
        logger.info(f"Successfully processed batch {i}")

    if not all_ids:
        raise Exception("Failed to store any documents in vector store")

    return all_ids
