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
from models.domain_objects import IngestionJob, IngestionStatus, IngestionType
from repository.ingestion_job_repo import IngestionJobRepository
from repository.ingestion_service import DocumentIngestionService
from repository.pipeline_ingest_documents import remove_document_from_vectorstore
from repository.rag_document_repo import RagDocumentRepository
from repository.vector_store_repo import VectorStoreRepository
from utilities.bedrock_kb import delete_document_from_kb
from utilities.common_functions import retry_config
from utilities.repository_types import RepositoryType

ingestion_service = DocumentIngestionService()
ingestion_job_repository = IngestionJobRepository()
vs_repo = VectorStoreRepository()

logger = logging.getLogger(__name__)

s3 = boto3.client("s3", region_name=os.environ["AWS_REGION"], config=retry_config)
bedrock_agent = boto3.client("bedrock-agent", region_name=os.environ["AWS_REGION"], config=retry_config)
rag_document_repository = RagDocumentRepository(os.environ["RAG_DOCUMENT_TABLE"], os.environ["RAG_SUB_DOCUMENT_TABLE"])


def pipeline_delete(job: IngestionJob) -> None:
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
