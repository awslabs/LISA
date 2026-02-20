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

"""Lambda event handlers for pipeline document ingestion and deletion."""

import logging
import os
from datetime import timedelta
from typing import Any, cast

import boto3
from models.domain_objects import (
    FixedChunkingStrategy,
    IngestionJob,
    IngestionStatus,
    IngestionType,
    NoneChunkingStrategy,
)
from repository.collection_service import CollectionService
from repository.ingestion_job_repo import IngestionJobRepository
from repository.ingestion_service import DocumentIngestionService
from repository.metadata_generator import MetadataGenerator
from repository.rag_document_repo import RagDocumentRepository
from repository.vector_store_repo import VectorStoreRepository
from utilities.auth import get_username
from utilities.common_functions import retry_config
from utilities.repository_types import RepositoryType
from utilities.time import utc_now

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


def extract_chunk_strategy(pipeline_config: dict) -> FixedChunkingStrategy | NoneChunkingStrategy:
    if "chunkingStrategy" in pipeline_config and pipeline_config["chunkingStrategy"]:
        chunking_strategy = pipeline_config["chunkingStrategy"]
        chunk_type = chunking_strategy.get("type", "fixed")
        if chunk_type == "fixed":
            return cast(FixedChunkingStrategy, FixedChunkingStrategy.model_validate(chunking_strategy))
        else:
            raise ValueError(f"Unsupported chunking strategy type: {chunk_type}")
    elif "chunkSize" in pipeline_config and "chunkOverlap" in pipeline_config:
        return FixedChunkingStrategy(
            size=int(pipeline_config["chunkSize"]), overlap=int(pipeline_config["chunkOverlap"])
        )
    else:
        logger.warning("No chunking strategy found in pipeline config, using defaults")
        return FixedChunkingStrategy(size=512, overlap=51)


def handle_pipeline_ingest_event(event: dict[str, Any], context: Any) -> None:
    """Handle pipeline document ingestion."""
    logger.debug(f"Received event: {event}")

    detail = event.get("detail", {})
    bucket = detail.get("bucket", None)
    username = get_username(event)
    key = detail.get("key", None)

    if key and key.endswith(".metadata.json"):
        logger.warning(f"Metadata file event reached Lambda (should be filtered by EventBridge): {key}")
        return
    repository_id = detail.get("repositoryId", None)
    pipeline_config = detail.get("pipelineConfig", None)
    collection_id = detail.get("collectionId", None)
    s3_path = f"s3://{bucket}/{key}"

    repository = vs_repo.find_repository_by_id(repository_id)

    if RepositoryType.is_type(repository, RepositoryType.BEDROCK_KB):
        if not collection_id:
            bedrock_config = repository.get("bedrockKnowledgeBaseConfig", {})
            data_sources = bedrock_config.get("dataSources", [])
            if data_sources:
                first_data_source = data_sources[0]
                collection_id_val: str | None = (
                    first_data_source.get("id") if isinstance(first_data_source, dict) else first_data_source.id
                )
                if not collection_id_val:
                    logger.error(f"Bedrock KB repository {repository_id} has invalid data source")
                    return
                collection_id = collection_id_val
            else:
                collection_id_val = bedrock_config.get("bedrockKnowledgeDatasourceId")
                if not collection_id_val:
                    logger.error(f"Bedrock KB repository {repository_id} missing data source ID")
                    return
                collection_id = collection_id_val

        if not collection_id:
            logger.error(f"Bedrock KB repository {repository_id} missing data source ID")
            return

        embedding_model = repository.get("embeddingModelId")
        chunk_strategy = NoneChunkingStrategy()
        username = "system"
        ingestion_type = IngestionType.AUTO

        logger.info(
            f"Processing Bedrock KB document {s3_path} for repository {repository_id}, collection {collection_id}"
        )
    else:
        embedding_model = pipeline_config.get("embeddingModel", None)

        if collection_id:
            collection = collection_service.get_collection(
                collection_id=collection_id, repository_id=repository_id, is_admin=True, username="", user_groups=[]
            )
            if collection.embeddingModel is not None:
                embedding_model = collection.embeddingModel
        else:
            collection_id = embedding_model

        chunk_strategy = extract_chunk_strategy(pipeline_config)
        ingestion_type = IngestionType.MANUAL

        logger.info(f"Ingesting object {s3_path} for repository {repository_id}/{embedding_model}")

    collection_dict = None
    if collection_id and collection_id != embedding_model:
        try:
            collection_obj = collection_service.get_collection(
                collection_id=collection_id, repository_id=repository_id, is_admin=True, username="", user_groups=[]
            )
            collection_dict = collection_obj.model_dump() if collection_obj else None
        except Exception as e:
            logger.warning(f"Could not fetch collection for metadata merging: {e}")

    merged_metadata = MetadataGenerator.merge_metadata(
        repository=repository,
        collection=collection_dict,
        document_metadata=None,
        for_bedrock_kb=False,
    )

    job = IngestionJob(
        repository_id=repository_id,
        collection_id=collection_id,
        embedding_model=embedding_model,
        chunk_strategy=chunk_strategy,
        s3_path=s3_path,
        username=username,
        ingestion_type=ingestion_type,
        metadata=merged_metadata,
    )
    ingestion_job_repository.save(job)
    ingestion_service.submit_create_job(job)

    logger.info(f"Submitted ingestion job for document {s3_path} in repository {repository_id}")


def handle_pipline_ingest_schedule(event: dict[str, Any], context: Any) -> None:
    """Lists objects modified in the last 24 hours and submits ingestion jobs."""
    logger.debug(f"Received event: {event}")

    detail = event.get("detail", {})
    bucket = detail.get("bucket", None)
    username = get_username(event)
    prefix = detail.get("prefix", None)
    repository_id = detail.get("repositoryId", None)
    pipeline_config = detail.get("pipelineConfig", None)
    embedding_model = pipeline_config.get("embeddingModel", None)

    chunk_strategy = extract_chunk_strategy(pipeline_config)

    repository = vs_repo.find_repository_by_id(repository_id)

    try:
        logger.info(f"Processing request for bucket: {bucket}, prefix: {prefix}")

        twenty_four_hours_ago = utc_now() - timedelta(hours=24)
        modified_keys = []
        paginator = s3.get_paginator("list_objects_v2")

        logger.info(f"Listing objects in {bucket}{prefix} modified after {twenty_four_hours_ago}")

        try:
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                if "Contents" not in page:
                    logger.info(f"No contents found in page for {bucket}{prefix}")
                    continue
                for obj in page["Contents"]:
                    last_modified = obj["LastModified"]
                    if last_modified >= twenty_four_hours_ago:
                        logger.info(f"Found modified file: {obj['Key']} (Last Modified: {last_modified})")
                        modified_keys.append(obj["Key"])
                    else:
                        logger.debug(
                            f"Skipping file {obj['Key']} - Last modified {last_modified}"
                            f" before cutoff {twenty_four_hours_ago}"
                        )
        except Exception as e:
            logger.error(f"Error during S3 list operation: {str(e)}", exc_info=True)
            raise

        merged_metadata = MetadataGenerator.merge_metadata(
            repository=repository,
            collection=None,
            document_metadata=None,
            for_bedrock_kb=False,
        )

        for key in modified_keys:
            job = IngestionJob(
                repository_id=repository_id,
                collection_id=embedding_model,
                chunk_strategy=chunk_strategy,
                s3_path=f"s3://{bucket}/{key}",
                username=username,
                ingestion_type=IngestionType.AUTO,
                metadata=merged_metadata,
            )
            ingestion_job_repository.save(job)
            ingestion_service.submit_create_job(job)

        logger.info(f"Found {len(modified_keys)} modified files in {bucket}{prefix}")
    except Exception as e:
        logger.error(f"Error listing objects: {str(e)}", exc_info=True)
        raise e


def handle_pipeline_delete_event(event: dict[str, Any], context: Any) -> None:
    """Handle pipeline document deletion for S3 ObjectRemoved events."""
    logger.debug(f"Received event: {event}")

    detail = event.get("detail", {})
    bucket = detail.get("bucket", None)
    key = detail.get("key", None)
    repository_id = detail.get("repositoryId", None)
    collection_id = detail.get("collectionId", None)
    pipeline_config = detail.get("pipelineConfig", None)
    s3_path = f"s3://{bucket}/{key}"

    if not repository_id:
        logger.warning("No repository_id in event, skipping deletion")
        return

    repository = vs_repo.find_repository_by_id(repository_id)
    if not repository:
        logger.warning(f"Repository {repository_id} not found, skipping deletion")
        return

    if RepositoryType.is_type(repository, RepositoryType.BEDROCK_KB):
        if not collection_id:
            bedrock_config = repository.get("bedrockKnowledgeBaseConfig", {})
            data_sources = bedrock_config.get("dataSources", [])
            if data_sources:
                first_data_source = data_sources[0]
                collection_id = (
                    first_data_source.get("id") if isinstance(first_data_source, dict) else first_data_source.id
                )
            else:
                collection_id = bedrock_config.get("bedrockKnowledgeDatasourceId")

        if not collection_id:
            logger.error(f"Bedrock KB repository {repository_id} missing data source ID")
            return

        logger.info(
            f"Processing Bedrock KB document deletion {s3_path}"
            f" for repository {repository_id}, collection {collection_id}"
        )
    else:
        if not pipeline_config or not isinstance(pipeline_config, dict):
            logger.warning("No pipeline_config in event, skipping deletion")
            return

        embedding_model = pipeline_config.get("embeddingModel", None)
        if embedding_model is None:
            logger.warning("No embedding_model in pipeline_config, skipping deletion")
            return

        collection_id = embedding_model
        logger.info(f"Deleting object {s3_path} for repository {repository_id}/{embedding_model}")

    documents = rag_document_repository.find_by_source(
        repository_id=repository_id,
        collection_id=collection_id,
        document_source=s3_path,
        join_docs=False,
    )

    if not documents:
        logger.info(f"Document {s3_path} not found in tracking system, already deleted or never tracked")
        return

    for rag_document in documents:
        logger.info(f"Deleting tracked document {rag_document.document_id} from {s3_path}")

        ingestion_job = ingestion_job_repository.find_by_document(rag_document.document_id)
        if ingestion_job is None:
            ingestion_job = IngestionJob(
                repository_id=repository_id,
                collection_id=collection_id,
                embedding_model=collection_id,
                chunk_strategy=None,
                s3_path=rag_document.source,
                username=rag_document.username,
                ingestion_type=IngestionType.AUTO,
                status=IngestionStatus.DELETE_PENDING,
            )
            ingestion_job_repository.save(ingestion_job)

        ingestion_service.create_delete_job(ingestion_job)
        logger.info(f"Submitted deletion job for document {s3_path} in repository {repository_id}")
