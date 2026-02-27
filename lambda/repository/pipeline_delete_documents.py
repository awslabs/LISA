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

import boto3
from boto3.dynamodb.conditions import Key
from models.domain_objects import CollectionStatus, IngestionJob, IngestionStatus, JobActionType
from repository.collection_repo import CollectionRepository
from repository.ingestion_job_repo import IngestionJobRepository
from repository.ingestion_service import DocumentIngestionService
from repository.pipeline_ingest_documents import remove_document_from_vectorstore
from repository.rag_document_repo import RagDocumentRepository
from repository.services.repository_service_factory import RepositoryServiceFactory
from repository.vector_store_repo import VectorStoreRepository
from utilities.bedrock_kb import bulk_delete_documents_from_kb, delete_document_from_kb
from utilities.common_functions import retry_config
from utilities.repository_types import RepositoryType

ingestion_service = DocumentIngestionService()
ingestion_job_repository = IngestionJobRepository()
vs_repo = VectorStoreRepository()

logger = logging.getLogger(__name__)

s3 = boto3.client("s3", region_name=os.environ["AWS_REGION"], config=retry_config)
bedrock_agent = boto3.client("bedrock-agent", region_name=os.environ["AWS_REGION"], config=retry_config)
rag_document_repository = RagDocumentRepository(os.environ["RAG_DOCUMENT_TABLE"], os.environ["RAG_SUB_DOCUMENT_TABLE"])
collection_repo = CollectionRepository()


def drop_opensearch_index(repository_id: str, collection_id: str) -> None:
    """Drop OpenSearch index using repository service.

    Args:
        repository_id: Repository ID
        collection_id: Collection ID
    """
    try:
        logger.info(f"Dropping OpenSearch index for collection {collection_id}")

        repository = vs_repo.find_repository_by_id(repository_id)
        service = RepositoryServiceFactory.create_service(repository)

        # Delegate to service layer
        service.delete_collection(collection_id, s3_client=s3)

    except Exception as e:
        logger.error(f"Failed to drop OpenSearch index: {e}", exc_info=True)
        # Don't raise - continue with document deletion even if index drop fails


def drop_pgvector_collection(repository_id: str, collection_id: str) -> None:
    """Drop PGVector collection using repository service.

    Args:
        repository_id: Repository ID
        collection_id: Collection ID
    """
    try:
        logger.info(f"Dropping PGVector collection for {collection_id}")

        repository = vs_repo.find_repository_by_id(repository_id)
        service = RepositoryServiceFactory.create_service(repository)

        # Delegate to service layer
        service.delete_collection(collection_id, s3_client=s3)

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
            drop_opensearch_index(job.repository_id, job.collection_id)  # type: ignore[arg-type]
        elif RepositoryType.is_type(repository, RepositoryType.PGVECTOR):
            drop_pgvector_collection(job.repository_id, job.collection_id)  # type: ignore[arg-type]
        elif RepositoryType.is_type(repository, RepositoryType.BEDROCK_KB):
            # For Bedrock KB, use bulk delete for efficiency
            # Only delete LISA-managed documents (MANUAL/AUTO), preserve EXISTING
            logger.info("Bedrock KB collection - bulk deleting LISA-managed documents from knowledge base")
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

            logger.info(f"Found {len(documents)} total documents in collection")

            # Separate by ingestion type
            lisa_managed = [doc for doc in documents if doc.get("ingestion_type") in ["manual", "auto"]]
            user_managed = [doc for doc in documents if doc.get("ingestion_type") == "existing"]

            logger.info(
                f"Collection {job.collection_id}: "
                f"lisa_managed={len(lisa_managed)}, user_managed={len(user_managed)}"
            )

            # Extract S3 paths for LISA-managed documents only
            s3_paths = [doc.get("source", "") for doc in lisa_managed if doc.get("source")]

            if s3_paths:
                try:
                    bulk_delete_documents_from_kb(
                        s3_client=s3,
                        bedrock_agent_client=bedrock_agent,
                        repository=repository,
                        s3_paths=s3_paths,
                        data_source_id=job.collection_id,
                    )
                    logger.info(
                        f"Successfully bulk deleted {len(s3_paths)} LISA-managed documents from KB, "
                        f"preserved {len(user_managed)} user-managed documents"
                    )
                except Exception as e:
                    logger.error(f"Failed to bulk delete documents from Bedrock KB: {e}")
                    # Continue with DynamoDB deletion even if KB deletion fails
            else:
                logger.info("No LISA-managed documents to delete from KB")

        # Delete all documents and subdocuments from DynamoDB
        # This method handles pagination and batch deletion
        logger.info(f"Deleting all documents from DynamoDB for collection {job.collection_id}")
        rag_document_repository.delete_all(job.repository_id, job.collection_id)  # type: ignore[arg-type]
        logger.info("Successfully deleted all documents from DynamoDB")

        # Delete collection DB entry
        is_default_collection = job.embedding_model is not None
        if not is_default_collection:
            collection_repo.delete(job.collection_id, job.repository_id)  # type: ignore[arg-type]

        # Update job status
        ingestion_job_repository.update_status(job, IngestionStatus.DELETE_COMPLETED)
        logger.info(f"Successfully deleted collection {job.collection_id}")

    except Exception as e:
        ingestion_job_repository.update_status(job, IngestionStatus.DELETE_FAILED)
        logger.error(f"Failed to delete collection: {str(e)}", exc_info=True)

        # Update collection status to DELETE_FAILED
        try:
            collection_repo.update(
                job.collection_id,  # type: ignore[arg-type]
                job.repository_id,
                {"status": CollectionStatus.DELETE_FAILED},
            )
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
    if job.job_type == JobActionType.COLLECTION_DELETION:
        logger.info(f"Routing to collection deletion for job {job.id}")
        pipeline_delete_collection(job)
    elif job.job_type == JobActionType.DOCUMENT_BATCH_DELETION:
        logger.info(f"Routing to batch document deletion for job {job.id}")
        pipeline_delete_documents(job)
    else:
        # Default to single document deletion
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
        rag_document = rag_document_repository.find_by_id(job.document_id, join_docs=True)  # type: ignore[arg-type]

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


def pipeline_delete_documents(job: IngestionJob) -> None:
    """
    Delete multiple documents in batch (up to 100 at a time).

    Processes documents from document_ids field containing list of document IDs.

    Args:
        job: Ingestion job with batch deletion details
    """
    try:
        logger.info(f"Starting batch deletion for job {job.id}")

        # Extract document list from document_ids field
        if not job.document_ids:
            raise ValueError("Batch deletion job missing 'document_ids' field")

        document_ids = job.document_ids
        if not isinstance(document_ids, list):
            raise ValueError("'document_ids' must be a list")

        if len(document_ids) > 100:
            raise ValueError(f"Batch size {len(document_ids)} exceeds maximum of 100 documents")

        logger.info(f"Processing {len(document_ids)} documents in batch deletion")

        # Update job status
        ingestion_job_repository.update_status(job, IngestionStatus.DELETE_IN_PROGRESS)

        # Get repository for vector store operations
        repository = vs_repo.find_repository_by_id(job.repository_id)
        is_bedrock_kb = RepositoryType.is_type(repository, RepositoryType.BEDROCK_KB)

        # Process each document
        successful = 0
        failed = 0
        errors = []
        # For Bedrock KB, group S3 paths by data source (collection_id)
        s3_paths_by_data_source = {}  # type: ignore[var-annotated]

        for document_id in document_ids:
            try:
                # Find associated RagDocument
                rag_document = rag_document_repository.find_by_id(document_id, join_docs=True)

                if rag_document:
                    # For Bedrock KB, collect S3 paths for bulk deletion grouped by data source
                    if is_bedrock_kb:
                        data_source_id = rag_document.collection_id
                        if data_source_id not in s3_paths_by_data_source:
                            s3_paths_by_data_source[data_source_id] = []
                        s3_paths_by_data_source[data_source_id].append(rag_document.source)
                    else:
                        # Remove from vector store immediately for non-Bedrock
                        remove_document_from_vectorstore(rag_document)

                    # Remove from DDB
                    rag_document_repository.delete_by_id(rag_document.document_id)
                    successful += 1
                    logger.info(f"Successfully deleted document {document_id}")
                else:
                    # Document not found, count as successful (idempotent)
                    successful += 1
                    logger.warning(f"Document {document_id} not found, skipping")

            except Exception as e:
                failed += 1
                error_msg = f"Failed to delete document {document_id}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)

        # For Bedrock KB, perform bulk deletion per data source
        if is_bedrock_kb and s3_paths_by_data_source:
            for data_source_id, s3_paths in s3_paths_by_data_source.items():
                try:
                    bulk_delete_documents_from_kb(
                        s3_client=s3,
                        bedrock_agent_client=bedrock_agent,
                        repository=repository,
                        s3_paths=s3_paths,
                        data_source_id=data_source_id,
                    )
                    logger.info(
                        f"Successfully bulk deleted {len(s3_paths)} documents from Bedrock KB "
                        "data source {data_source_id}"
                    )
                except Exception as e:
                    logger.error(
                        "Failed to bulk delete from Bedrock KB data source %s: %s",
                        data_source_id,
                        e,
                        exc_info=True,
                    )
                    # Documents already deleted from DynamoDB, continue with partial success
                # This is acceptable because DynamoDB is source of truth

        # Update job with results in metadata
        if not job.metadata:
            job.metadata = {}
        job.metadata["results"] = {
            "successful": successful,
            "failed": failed,
            "errors": errors[:10],  # Limit error messages
        }

        if failed == 0:
            ingestion_job_repository.update_status(job, IngestionStatus.DELETE_COMPLETED)
            logger.info(f"Batch deletion completed: {successful} successful, {failed} failed")
        else:
            ingestion_job_repository.update_status(job, IngestionStatus.DELETE_FAILED)
            logger.warning(f"Batch deletion completed with errors: {successful} successful, {failed} failed")

    except Exception as e:
        ingestion_job_repository.update_status(job, IngestionStatus.DELETE_FAILED)
        error_msg = f"Failed to process batch deletion: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise Exception(error_msg)
