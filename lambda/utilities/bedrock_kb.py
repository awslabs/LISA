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

"""Utilities for handling Bedrock Knowledge Base specific operations.

This module centralizes logic related to repositories of type
"bedrock_knowledge_base" so that call sites can remain concise.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from models.domain_objects import (
    IngestionJob,
    IngestionType,
    JobActionType,
    NoneChunkingStrategy,
    RagCollectionConfig,
    RagDocument,
)

logger = logging.getLogger(__name__)


class S3DocumentDiscoveryResult:
    """Result of S3 document discovery operation."""

    def __init__(
        self,
        discovered: int = 0,
        skipped: int = 0,
        successful: int = 0,
        failed: int = 0,
        document_ids: Optional[List[str]] = None,
        errors: Optional[List[str]] = None,
    ):
        self.discovered = discovered
        self.skipped = skipped
        self.successful = successful
        self.failed = failed
        self.document_ids = document_ids or []
        self.errors = errors or []


class S3DocumentDiscoveryService:
    """Service for discovering and tracking existing documents in S3 buckets."""

    def __init__(
        self,
        s3_client: Any,
        bedrock_agent_client: Any,
        rag_document_repository: Any,
        metadata_generator: Any,
        s3_metadata_manager: Any,
        collection_service: Any,
        vector_store_repo: Any,
    ):
        """Initialize S3 document discovery service.

        Args:
            s3_client: boto3 S3 client
            bedrock_agent_client: boto3 bedrock-agent client
            rag_document_repository: Repository for RagDocument persistence
            metadata_generator: MetadataGenerator instance
            s3_metadata_manager: S3MetadataManager instance
            collection_service: CollectionService instance
            vector_store_repo: VectorStoreRepository instance
        """
        self.s3_client = s3_client
        self.bedrock_agent_client = bedrock_agent_client
        self.rag_document_repository = rag_document_repository
        self.metadata_generator = metadata_generator
        self.s3_metadata_manager = s3_metadata_manager
        self.collection_service = collection_service
        self.vector_store_repo = vector_store_repo

    def discover_and_ingest_documents(
        self,
        repository_id: str,
        collection_id: str,
        s3_bucket: str,
        s3_prefix: str = "",
        ingestion_type: IngestionType = IngestionType.EXISTING,
    ) -> S3DocumentDiscoveryResult:
        """
        Discover and ingest existing documents from S3 bucket.

        Scans S3 bucket, creates metadata.json files, creates RagDocument entries,
        and triggers Bedrock KB sync.

        Args:
            repository_id: Repository identifier
            collection_id: Collection identifier
            s3_bucket: S3 bucket to scan
            s3_prefix: Optional S3 prefix to scan within bucket
            ingestion_type: Type of ingestion (default: EXISTING)

        Returns:
            S3DocumentDiscoveryResult with operation statistics
        """
        logger.info(f"Starting S3 document discovery for bucket {s3_bucket} with prefix '{s3_prefix}'")

        result = S3DocumentDiscoveryResult()

        try:
            # Get repository configuration
            repository = self.vector_store_repo.find_repository_by_id(repository_id)

            # Get collection for metadata generation
            collection = self._get_collection(repository_id, collection_id)

            # Scan S3 bucket for documents
            documents_to_process, skipped_count = self._scan_s3_bucket(s3_bucket, s3_prefix)
            result.discovered = len(documents_to_process)
            result.skipped = skipped_count

            if not documents_to_process:
                logger.info(f"No valid documents found in S3 bucket {s3_bucket} with prefix '{s3_prefix}'")
                return result

            logger.info(f"Found {len(documents_to_process)} documents to process")

            # Process each document
            for document_key in documents_to_process:
                try:
                    s3_path = f"s3://{s3_bucket}/{document_key}"

                    # Check if document already exists (idempotent)
                    if self._document_exists(repository_id, collection_id, s3_path):
                        existing_doc = next(
                            self.rag_document_repository.find_by_source(
                                repository_id, collection_id, s3_path, join_docs=False
                            )
                        )
                        result.document_ids.append(existing_doc.document_id)
                        result.successful += 1
                        logger.info(f"Document {s3_path} already tracked, skipping")
                        continue

                    # Create metadata.json file
                    self._create_metadata_file(
                        repository=repository,
                        collection=collection,
                        s3_bucket=s3_bucket,
                        document_key=document_key,
                        repository_id=repository_id,
                        collection_id=collection_id,
                    )

                    # Create RagDocument entry
                    document_id = self._create_rag_document(
                        repository_id=repository_id,
                        collection_id=collection_id,
                        s3_path=s3_path,
                        ingestion_type=ingestion_type,
                    )

                    result.document_ids.append(document_id)
                    result.successful += 1
                    logger.info(f"Tracked existing document {s3_path}")

                except Exception as e:
                    result.failed += 1
                    error_msg = f"Failed to process {document_key}: {str(e)}"
                    logger.error(error_msg, exc_info=True)
                    result.errors.append(error_msg)

            # Trigger Bedrock KB sync if documents were processed
            if result.successful > 0:
                self._trigger_kb_sync(repository, collection_id, result.successful)

            logger.info(
                f"S3 discovery completed: {result.successful} successful, "
                f"{result.failed} failed, {result.skipped} skipped"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to discover S3 documents: {str(e)}", exc_info=True)
            raise

    def _scan_s3_bucket(self, s3_bucket: str, s3_prefix: str) -> Tuple[List[str], int]:
        """
        Scan S3 bucket and return list of document keys.

        Args:
            s3_bucket: S3 bucket name
            s3_prefix: S3 prefix to scan

        Returns:
            Tuple of (document_keys, skipped_count)
        """
        list_params = {"Bucket": s3_bucket, "Delimiter": "/"}
        if s3_prefix:
            list_params["Prefix"] = s3_prefix if s3_prefix.endswith("/") else f"{s3_prefix}/"

        response = self.s3_client.list_objects_v2(**list_params)

        if "Contents" not in response:
            return [], 0

        documents_to_process = []
        skipped_count = 0

        for obj in response["Contents"]:
            key = obj["Key"]
            # Skip metadata files and directories
            if key.endswith("/") or key.endswith(".metadata.json"):
                skipped_count += 1
                continue
            documents_to_process.append(key)

        return documents_to_process, skipped_count

    def _get_collection(self, repository_id: str, collection_id: str) -> Optional[RagCollectionConfig]:
        """Get collection configuration."""
        try:
            return self.collection_service.get_collection(
                collection_id=collection_id,
                repository_id=repository_id,
                username="system",
                user_groups=[],
                is_admin=True,
            )
        except Exception as e:
            logger.warning(f"Could not fetch collection for metadata: {e}")
            return None

    def _document_exists(self, repository_id: str, collection_id: str, s3_path: str) -> bool:
        """Check if document already exists in repository."""
        existing_docs = list(
            self.rag_document_repository.find_by_source(repository_id, collection_id, s3_path, join_docs=False)
        )
        return len(existing_docs) > 0

    def _create_metadata_file(
        self,
        repository: Dict[str, Any],
        collection: Optional[RagCollectionConfig],
        s3_bucket: str,
        document_key: str,
        repository_id: str,
        collection_id: str,
    ) -> None:
        """Create and upload metadata.json file for document."""
        try:
            metadata_content = self.metadata_generator.generate_metadata_json(
                repository=repository,
                collection=collection,
                document_metadata=None,  # No document-specific metadata for existing docs
            )

            self.s3_metadata_manager.upload_metadata_file(
                s3_client=self.s3_client,
                bucket=s3_bucket,
                document_key=document_key,
                metadata_content=metadata_content,
                repository_id=repository_id,
                collection_id=collection_id,
            )
            logger.info(f"Created metadata file for s3://{s3_bucket}/{document_key}")
        except Exception as e:
            logger.error(f"Failed to create metadata for {document_key}: {str(e)}")
            # Continue - metadata is optional

    def _create_rag_document(
        self,
        repository_id: str,
        collection_id: str,
        s3_path: str,
        ingestion_type: IngestionType,
    ) -> str:
        """Create and save RagDocument entry."""
        rag_document = RagDocument(
            repository_id=repository_id,
            collection_id=collection_id,
            document_name=os.path.basename(s3_path),
            source=s3_path,
            subdocs=[],  # Empty - KB manages chunks internally
            chunk_strategy=NoneChunkingStrategy(),  # KB manages chunking
            username="system",  # System-discovered
            ingestion_type=ingestion_type,
        )
        self.rag_document_repository.save(rag_document)
        return rag_document.document_id

    def _trigger_kb_sync(self, repository: Dict[str, Any], collection_id: str, document_count: int) -> None:
        """Trigger Bedrock KB sync for ingested documents."""
        bedrock_config = repository.get("bedrockKnowledgeBaseConfig", {})
        knowledge_base_id = bedrock_config.get("bedrockKnowledgeBaseId")

        if not knowledge_base_id:
            logger.warning("No knowledge base ID found, skipping KB sync")
            return

        logger.info(f"Triggering Bedrock KB sync for collection {collection_id}")
        try:
            self.bedrock_agent_client.start_ingestion_job(
                knowledgeBaseId=knowledge_base_id,
                dataSourceId=collection_id,
            )
            logger.info(f"Successfully triggered KB sync for {document_count} documents")
        except Exception as e:
            logger.error(f"Failed to trigger KB sync: {str(e)}")
            # Don't fail - documents are already tracked


logger = logging.getLogger(__name__)


def ingest_document_to_kb(
    s3_client: Any,
    bedrock_agent_client: Any,
    job: IngestionJob,
    repository: Dict[str, Any],
) -> None:
    """
    Copy the source object into the KB datasource bucket and trigger ingestion. S3 will
    kick off another IngestionJob to store the document in the collection DB
    """
    bedrock_config = repository.get("bedrockKnowledgeBaseConfig", {})

    source_bucket = job.s3_path.split("/")[2]
    source_key = job.s3_path.split(source_bucket + "/")[1]

    s3_client.copy_object(
        CopySource={"Bucket": source_bucket, "Key": source_key},
        Bucket=bedrock_config.get("bedrockKnowledgeDatasourceS3Bucket", None),
        Key=os.path.basename(job.s3_path),
    )

    s3_client.delete_object(Bucket=source_bucket, Key=source_key)

    # Use collection_id from job as data source ID
    data_source_id = job.collection_id
    # Support both field names for backward compatibility
    kb_id = bedrock_config.get("bedrockKnowledgeBaseId") or bedrock_config.get("knowledgeBaseId")

    if not kb_id:
        logger.error(f"Repository {repository.get('repositoryId')} missing knowledge base ID")
        raise ValueError(
            "Bedrock KB repository is missing required field 'bedrockKnowledgeBaseId' or 'knowledgeBaseId'. "
            "Please update the repository configuration with the actual AWS Bedrock Knowledge Base ID."
        )

    bedrock_agent_client.start_ingestion_job(
        knowledgeBaseId=kb_id,
        dataSourceId=data_source_id,
    )


def delete_document_from_kb(
    s3_client: Any,
    bedrock_agent_client: Any,
    job: IngestionJob,
    repository: Dict[str, Any],
) -> None:
    """Remove the source object from the KB datasource bucket and re-sync the KB."""
    bedrock_config = repository.get("bedrockKnowledgeBaseConfig", {})

    s3_client.delete_object(
        Bucket=bedrock_config.get("bedrockKnowledgeDatasourceS3Bucket", None),
        Key=os.path.basename(job.s3_path),
    )

    # Use collection_id from job as data source ID
    data_source_id = job.collection_id
    # Support both field names for backward compatibility
    kb_id = bedrock_config.get("bedrockKnowledgeBaseId") or bedrock_config.get("knowledgeBaseId")

    if not kb_id:
        logger.error(f"Repository {repository.get('repositoryId')} missing knowledge base ID")
        raise ValueError(
            "Bedrock KB repository is missing required field 'bedrockKnowledgeBaseId' or 'knowledgeBaseId'. "
            "Please update the repository configuration with the actual AWS Bedrock Knowledge Base ID."
        )

    bedrock_agent_client.start_ingestion_job(
        knowledgeBaseId=kb_id,
        dataSourceId=data_source_id,
    )


def bulk_delete_documents_from_kb(
    s3_client: Any,
    bedrock_agent_client: Any,
    repository: Dict[str, Any],
    s3_paths: List[str],
    data_source_id: Optional[str] = None,
) -> None:
    """Bulk delete documents from KB datasource bucket and trigger single ingestion.

    Args:
        s3_client: boto3 S3 client
        bedrock_agent_client: boto3 bedrock-agent client
        repository: Repository configuration dictionary
        s3_paths: List of S3 paths to delete
        data_source_id: Optional data source ID. If not provided, will try to get from config.
    """
    bedrock_config = repository.get("bedrockKnowledgeBaseConfig", {})
    datasource_bucket = bedrock_config.get("bedrockKnowledgeDatasourceS3Bucket")

    # Batch delete from S3 (max 1000 per request)
    batch_size = 1000
    for i in range(0, len(s3_paths), batch_size):
        batch = s3_paths[i : i + batch_size]
        delete_objects = [{"Key": os.path.basename(path)} for path in batch]

        if delete_objects:
            s3_client.delete_objects(Bucket=datasource_bucket, Delete={"Objects": delete_objects})

    # Determine data source ID
    if not data_source_id:
        # Try new structure with dataSources array
        data_sources = bedrock_config.get("dataSources", [])
        if data_sources:
            first_data_source = data_sources[0]
            data_source_id = (
                first_data_source.get("id") if isinstance(first_data_source, dict) else first_data_source.id
            )
        else:
            # Try legacy single data source ID
            data_source_id = bedrock_config.get("bedrockKnowledgeDatasourceId")

    # Trigger single ingestion job to sync KB
    # Support both field names for backward compatibility
    kb_id = bedrock_config.get("bedrockKnowledgeBaseId") or bedrock_config.get("knowledgeBaseId")

    if not kb_id:
        logger.error(f"Repository {repository.get('repositoryId')} missing knowledge base ID")
        raise ValueError(
            "Bedrock KB repository is missing required field 'bedrockKnowledgeBaseId' or 'knowledgeBaseId'. "
            "Please update the repository configuration with the actual AWS Bedrock Knowledge Base ID."
        )

    bedrock_agent_client.start_ingestion_job(
        knowledgeBaseId=kb_id,
        dataSourceId=data_source_id,
    )


def create_s3_scan_job(
    ingestion_job_repository: Any,
    ingestion_service: Any,
    repository_id: str,
    collection_id: str,
    embedding_model: str,
    s3_bucket: str,
    s3_prefix: str = "",
) -> str:
    """
    Create a batch ingestion job to scan and ingest existing S3 documents.

    This creates a batch job with empty s3_paths that will be processed by
    pipeline_ingest_documents. The empty s3_paths signals that the S3 bucket
    should be scanned to discover existing documents.

    Args:
        ingestion_job_repository: Repository for saving ingestion jobs
        ingestion_service: Service for submitting jobs
        repository_id: Repository identifier
        collection_id: Collection identifier
        embedding_model: Embedding model identifier
        s3_bucket: S3 bucket to scan
        s3_prefix: Optional S3 prefix to scan within bucket

    Returns:
        Job ID of the created scan job
    """
    logger.info(f"Creating S3 scan job for bucket {s3_bucket} with prefix '{s3_prefix}'")

    # Store bucket/prefix in s3_path field for the scan job
    # Format: s3://bucket/prefix (or just s3://bucket if no prefix)
    scan_path = f"s3://{s3_bucket}/{s3_prefix}" if s3_prefix else f"s3://{s3_bucket}/"

    # Create batch job with empty s3_paths - this signals S3 scan mode
    job = IngestionJob(
        repository_id=repository_id,
        collection_id=collection_id,
        embedding_model=embedding_model,
        chunk_strategy=NoneChunkingStrategy(),
        s3_path=scan_path,  # Store scan location
        username="system",  # System-initiated
        ingestion_type=IngestionType.EXISTING,  # Mark as pre-existing documents
        job_type=JobActionType.DOCUMENT_BATCH_INGESTION,
        s3_paths=[],  # Empty list signals S3 scan mode
    )

    ingestion_job_repository.save(job)
    ingestion_service.submit_create_job(job)

    logger.info(f"Created S3 scan job {job.id} for bucket {s3_bucket}")
    return job.id
