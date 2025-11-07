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

import logging
import os
from typing import Any, Dict

import boto3
from boto3.dynamodb.conditions import Key
from models.domain_objects import CollectionStatus, DeletionJobType, IngestionJob, IngestionStatus, IngestionType
from repository.collection_repo import CollectionRepository
from repository.embeddings import RagEmbeddings
from repository.ingestion_job_repo import IngestionJobRepository
from repository.ingestion_service import DocumentIngestionService
from repository.pipeline_ingest_documents import remove_document_from_vectorstore
from repository.rag_document_repo import RagDocumentRepository
from repository.vector_store_repo import VectorStoreRepository
from utilities.bedrock_kb import bulk_delete_documents_from_kb, delete_document_from_kb
from utilities.common_functions import retry_config
from utilities.repository_types import RepositoryType
from utilities.vector_store import get_vector_store_client

ingestion_service = DocumentIngestionService()
ingestion_job_repository = IngestionJobRepository()
vs_repo = VectorStoreRepository()

logger = logging.getLogger(__name__)

s3 = boto3.client("s3", region_name=os.environ["AWS_REGION"], config=retry_config)
bedrock_agent = boto3.client("bedrock-agent", region_name=os.environ["AWS_REGION"], config=retry_config)
rag_document_repository = RagDocumentRepository(os.environ["RAG_DOCUMENT_TABLE"], os.environ["RAG_SUB_DOCUMENT_TABLE"])
collection_repo = CollectionRepository()


def drop_opensearch_index(repository_id: str, collection_id: str) -> None:
    """
    Drop OpenSearch index for a collection to speed up deletion.

    Args:
        repository_id: Repository ID
        collection_id: Collection ID
    """
    try:
        logger.info(f"Dropping OpenSearch index for collection {collection_id}")

        # Get vector store client
        embeddings = RagEmbeddings(model_name=collection_id)
        vector_store = get_vector_store_client(
            repository_id,
            collection_id=collection_id,
            embeddings=embeddings,
        )

        # Drop the index if it exists
        if hasattr(vector_store, "client") and hasattr(vector_store.client, "indices"):
            index_name = f"{repository_id}_{collection_id}".lower()
            if vector_store.client.indices.exists(index=index_name):
                vector_store.client.indices.delete(index=index_name)
                logger.info(f"Successfully dropped OpenSearch index: {index_name}")
            else:
                logger.info(f"OpenSearch index {index_name} does not exist")
        else:
            logger.warning("Vector store client does not support index operations")

    except Exception as e:
        logger.error(f"Failed to drop OpenSearch index: {e}", exc_info=True)
        # Don't raise - continue with document deletion even if index drop fails


def drop_pgvector_collection(repository_id: str, collection_id: str) -> None:
    """
    Drop PGVector collection table/schema to speed up deletion.

    Args:
        repository_id: Repository ID
        collection_id: Collection ID
    """
    try:
        logger.info(f"Dropping PGVector collection for {collection_id}")

        # Get vector store client
        embeddings = RagEmbeddings(model_name=collection_id)
        vector_store = get_vector_store_client(
            repository_id,
            collection_id=collection_id,
            embeddings=embeddings,
        )

        # Drop the collection if supported
        if hasattr(vector_store, "delete_collection"):
            vector_store.delete_collection()
            logger.info(f"Successfully dropped PGVector collection: {collection_id}")
        else:
            logger.warning("Vector store does not support collection deletion")

    except Exception as e:
        logger.error(f"Failed to drop PGVector collection: {e}", exc_info=True)
        # Don't raise - continue with document deletion even if collection drop fails


def pipeline_delete_collection(job: IngestionJob) -> None:
    """
    Delete all documents in a collection.

    Steps:
    1. Drop vector store index for collection (if supported)
    2. Delete all documents from DynamoDB (which also handles subdocuments)
    3. Update collection status to DELETED

    Note: Dropping the index removes all embeddings, so we don't need to
    delete them individually from the vector store.

    Args:
        job: Ingestion job with collection deletion details
    """
    try:
        logger.info(f"Deleting collection {job.collection_id} in repository {job.repository_id}")

        repository = vs_repo.find_repository_by_id(job.repository_id)

        # Drop index for faster cleanup (OpenSearch/PGVector)
        # This removes all embeddings from the vector store
        if RepositoryType.is_type(repository, RepositoryType.OPENSEARCH):
            drop_opensearch_index(job.repository_id, job.collection_id)
        elif RepositoryType.is_type(repository, RepositoryType.PGVECTOR):
            drop_pgvector_collection(job.repository_id, job.collection_id)
        elif RepositoryType.is_type(repository, RepositoryType.BEDROCK_KB):
            # For Bedrock KB, use bulk delete for efficiency
            logger.info("Bedrock KB collection - bulk deleting documents from knowledge base")
            pk = f"{job.repository_id}#{job.collection_id}"

            dynamodb = boto3.resource("dynamodb")
            doc_table = dynamodb.Table(os.environ["RAG_DOCUMENT_TABLE"])

            response = doc_table.query(KeyConditionExpression=Key("pk").eq(pk))
            documents = response.get("Items", [])

            # Continue pagination if needed
            while "LastEvaluatedKey" in response:
                response = doc_table.query(
                    KeyConditionExpression=Key("pk").eq(pk), ExclusiveStartKey=response["LastEvaluatedKey"]
                )
                documents.extend(response.get("Items", []))

            logger.info(f"Found {len(documents)} documents to bulk delete from Bedrock KB")

            # Extract S3 paths for bulk deletion
            s3_paths = [doc.get("source", "") for doc in documents if doc.get("source")]

            if s3_paths:
                try:
                    bulk_delete_documents_from_kb(
                        s3_client=s3,
                        bedrock_agent_client=bedrock_agent,
                        repository=repository,
                        s3_paths=s3_paths,
                    )
                    logger.info(f"Successfully bulk deleted {len(s3_paths)} documents from Bedrock KB")
                except Exception as e:
                    logger.error(f"Failed to bulk delete documents from Bedrock KB: {e}")
                    # Continue with DynamoDB deletion even if KB deletion fails

        # Delete all documents and subdocuments from DynamoDB
        # This method handles pagination and batch deletion
        logger.info(f"Deleting all documents from DynamoDB for collection {job.collection_id}")
        rag_document_repository.delete_all(job.repository_id, job.collection_id)
        logger.info("Successfully deleted all documents from DynamoDB")

        # Update collection status to DELETED
        collection_repo.update(job.collection_id, job.repository_id, {"status": CollectionStatus.DELETED})

        # Update job status
        ingestion_job_repository.update_status(job, IngestionStatus.DELETE_COMPLETED)
        logger.info(f"Successfully deleted collection {job.collection_id}")

    except Exception as e:
        ingestion_job_repository.update_status(job, IngestionStatus.DELETE_FAILED)
        logger.error(f"Failed to delete collection: {str(e)}", exc_info=True)

        # Update collection status to DELETE_FAILED
        try:
            collection_repo.update(job.collection_id, job.repository_id, {"status": CollectionStatus.DELETE_FAILED})
        except Exception as update_error:
            logger.error(f"Failed to update collection status: {update_error}")

        raise


def pipeline_delete(job: IngestionJob) -> None:
    """
    Route deletion job to appropriate handler based on job type.

    Args:
        job: Ingestion job with deletion details
    """
    # Check job type and route accordingly
    if job.job_type == DeletionJobType.COLLECTION_DELETION:
        logger.info(f"Routing to collection deletion for job {job.id}")
        pipeline_delete_collection(job)
    else:
        # Default to document deletion
        logger.info(f"Routing to document deletion for job {job.id}")
        pipeline_delete_document(job)


def pipeline_delete_document(job: IngestionJob) -> None:
    """
    Delete a single document.

    Args:
        job: Ingestion job with document deletion details
    """
    try:
        logger.info(f"Deleting document {job.s3_path} for repository {job.repository_id}")

        # Find associated RagDocument
        rag_document = rag_document_repository.find_by_id(job.document_id, join_docs=True)

        if rag_document:
            # Actually remove from vector store
            repository = vs_repo.find_repository_by_id(job.repository_id)
            if RepositoryType.is_type(repository, RepositoryType.BEDROCK_KB):
                delete_document_from_kb(
                    s3_client=s3,
                    bedrock_agent_client=bedrock_agent,
                    job=job,
                    repository=repository,
                )
            else:
                remove_document_from_vectorstore(rag_document)

            # Remove from DDB
            rag_document_repository.delete_by_id(rag_document.document_id)

            # Update status
            ingestion_job_repository.update_status(job, IngestionStatus.DELETE_COMPLETED)
            logger.info(f"Successfully deleted {job.s3_path} from S3")
        else:
            # If no document found, still update status to completed
            ingestion_job_repository.update_status(job, IngestionStatus.DELETE_COMPLETED)
    except Exception as e:
        ingestion_job_repository.update_status(job, IngestionStatus.DELETE_FAILED)

        error_msg = f"Failed to delete document: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise Exception(error_msg)


def handle_pipeline_delete_event(event: Dict[str, Any], context: Any) -> None:
    """TODO: Update to handle collection"""
    """Handle pipeline document ingestion."""

    # Extract and validate inputs
    logger.debug(f"Received event: {event}")

    detail = event.get("detail", {})
    bucket = detail.get("bucket", None)
    key = detail.get("key", None)
    repository_id = detail.get("repositoryId", None)
    pipeline_config = detail.get("pipelineConfig", None)
    if not pipeline_config or not isinstance(pipeline_config, dict):
        # If pipeline_config is missing or not a dict, skip
        return
    embedding_model = pipeline_config.get("embeddingModel", None)
    if embedding_model is None:
        # If embedding_model is missing, skip
        return
    s3_key = f"s3://{bucket}/{key}"

    logger.info(f"Deleting object {s3_key} for repository {repository_id}/{embedding_model}")

    # Currently there could be RagDocuments without a corresponding IngestionJob, so lookup by RagDocument first
    # and then find or create the corresponding IngestionJob. In the future it should be possible to lookup
    # directly by IngestionJob
    for rag_document in rag_document_repository.find_by_source(
        repository_id=repository_id, collection_id=embedding_model, document_source=s3_key, join_docs=True
    ):
        logger.info(f"deleting doc {rag_document.model_dump()}")
        ingestion_job = ingestion_job_repository.find_by_document(rag_document.document_id)
        if ingestion_job is None:
            ingestion_job = IngestionJob(
                repository_id=repository_id,
                collection_id=embedding_model,
                embedding_model=embedding_model,
                chunk_strategy=None,
                s3_path=rag_document.source,
                username=rag_document.username,
                ingestion_type=IngestionType.AUTO,
                status=IngestionStatus.DELETE_PENDING,
            )

        ingestion_service.create_delete_job(ingestion_job)
        logger.info(f"Deleting document {s3_key} for repository {ingestion_job.repository_id}")
