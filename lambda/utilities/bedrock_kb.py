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
from typing import Any, Dict, List, Optional

from models.domain_objects import IngestionJob, IngestionType, JobActionType, NoneChunkingStrategy

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

    bedrock_agent_client.start_ingestion_job(
        knowledgeBaseId=bedrock_config.get("bedrockKnowledgeBaseId", None),
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

    bedrock_agent_client.start_ingestion_job(
        knowledgeBaseId=bedrock_config.get("bedrockKnowledgeBaseId", None),
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
    bedrock_agent_client.start_ingestion_job(
        knowledgeBaseId=bedrock_config.get("bedrockKnowledgeBaseId"),
        dataSourceId=data_source_id,
    )


def ingest_bedrock_s3_documents(
    s3_client: Any,
    ingestion_job_repository: Any,
    ingestion_service: Any,
    repository_id: str,
    collection_id: str,
    s3_bucket: str,
    embedding_model: str,
) -> tuple[int, int]:
    """
    Discover and index existing documents in Bedrock KB S3 bucket.

    Scans S3 bucket for existing documents and creates tracking records
    with ingestion_type=EXISTING to indicate they are user-managed.

    Only scans depth 1 (root level) and ignores metadata files.
    Creates multiple batch jobs if more than 100 documents found.

    Args:
        s3_client: boto3 S3 client
        ingestion_job_repository: Repository for saving ingestion jobs
        ingestion_service: Service for submitting jobs
        repository_id: Repository identifier
        collection_id: Collection identifier
        s3_bucket: S3 bucket to scan
        embedding_model: Embedding model identifier

    Returns:
        Tuple of (discovered_count, skipped_count)
    """
    discovered_count = 0
    skipped_count = 0

    try:
        # List objects at root level only
        response = s3_client.list_objects_v2(Bucket=s3_bucket, Delimiter="/")

        if "Contents" not in response:
            logger.info(f"No documents found in S3 bucket {s3_bucket}")
            return (0, 0)

        # Filter out metadata files and collect document paths
        document_paths = []
        for obj in response["Contents"]:
            key = obj["Key"]
            # Skip metadata files and directories
            if key.endswith("/") or key.endswith(".metadata.json"):
                skipped_count += 1
                continue
            document_paths.append(f"s3://{s3_bucket}/{key}")

        if not document_paths:
            logger.info(f"No valid documents found in S3 bucket {s3_bucket}")
            return (0, skipped_count)

        logger.info(f"Found {len(document_paths)} documents to discover and index")
        discovered_count = len(document_paths)

        # Create batch jobs (max 100 documents per job)
        # Mark as EXISTING to indicate pre-existing user-managed documents
        batch_size = 100
        for i in range(0, len(document_paths), batch_size):
            batch = document_paths[i : i + batch_size]

            job = IngestionJob(
                repository_id=repository_id,
                collection_id=collection_id,
                embedding_model=embedding_model,
                chunk_strategy=NoneChunkingStrategy(),
                s3_path="",  # Not used for batch jobs
                username="system",  # System-discovered
                ingestion_type=IngestionType.EXISTING,  # Mark as pre-existing
                job_type=JobActionType.DOCUMENT_BATCH_INGESTION,
                s3_paths=batch,
            )

            ingestion_job_repository.save(job)
            ingestion_service.submit_create_job(job)
            logger.info(
                f"Created discovery job {job.id} for {len(batch)} EXISTING documents " f"(batch {i // batch_size + 1})"
            )

        logger.info(f"Document discovery complete: discovered={discovered_count}, skipped={skipped_count}")
        return (discovered_count, skipped_count)

    except Exception as e:
        logger.error(f"Failed to scan S3 bucket {s3_bucket}: {str(e)}", exc_info=True)
        # Don't raise - collection creation should succeed even if discovery fails
        return (discovered_count, skipped_count)
