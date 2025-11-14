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
from typing import Any, Dict, List

from models.domain_objects import IngestionJob, PipelineConfig, PipelineTrigger, VectorStoreConfig

logger = logging.getLogger(__name__)


def retrieve_documents(
    bedrock_runtime_client: Any,
    repository: Dict[str, Any],
    query: str,
    top_k: int,
    repository_id: str,
) -> List[Dict[str, Any]]:
    """Retrieve documents from Bedrock Knowledge Base.

    Args:
        bedrock_runtime_client: boto3 bedrock-agent-runtime client
        repository: Repository configuration dictionary
        query: Text query to search
        top_k: Number of results to return
        repository_id: Repository identifier to include in metadata

    Returns:
        List of documents in the format expected by callers
    """
    bedrock_config = repository.get("bedrockKnowledgeBaseConfig", {})

    response = bedrock_runtime_client.retrieve(
        knowledgeBaseId=bedrock_config.get("bedrockKnowledgeBaseId", None),
        retrievalQuery={"text": query},
        retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": int(top_k)}},
    )

    docs: List[Dict[str, Any]] = []
    for doc in response.get("retrievalResults", []):
        uri = (doc.get("location", {}) or {}).get("s3Location", {}).get("uri")
        name = uri.split("/")[-1] if uri else None
        docs.append(
            {
                "page_content": (doc.get("content", {}) or {}).get("text", ""),
                "metadata": {
                    "source": uri,
                    "name": name,
                    "repository_id": repository_id,
                },
            }
        )

    return docs


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

    bedrock_agent_client.start_ingestion_job(
        knowledgeBaseId=bedrock_config.get("bedrockKnowledgeBaseId", None),
        dataSourceId=bedrock_config.get("bedrockKnowledgeDatasourceId", None),
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
    bedrock_agent_client.start_ingestion_job(
        knowledgeBaseId=bedrock_config.get("bedrockKnowledgeBaseId", None),
        dataSourceId=bedrock_config.get("bedrockKnowledgeDatasourceId", None),
    )


def bulk_delete_documents_from_kb(
    s3_client: Any,
    bedrock_agent_client: Any,
    repository: Dict[str, Any],
    s3_paths: List[str],
) -> None:
    """Bulk delete documents from KB datasource bucket and trigger single ingestion.

    Args:
        s3_client: boto3 S3 client
        bedrock_agent_client: boto3 bedrock-agent client
        repository: Repository configuration dictionary
        s3_paths: List of S3 paths to delete
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

    # Trigger single ingestion job to sync KB
    bedrock_agent_client.start_ingestion_job(
        knowledgeBaseId=bedrock_config.get("bedrockKnowledgeBaseId"),
        dataSourceId=bedrock_config.get("bedrockKnowledgeDatasourceId"),
    )


def add_default_pipeline_for_bedrock_kb(vector_store_config: VectorStoreConfig) -> None:
    """Add default pipeline configuration for Bedrock Knowledge Base repositories.

    Automatically adds a default event-driven pipeline if none exists, using the
    datasource S3 bucket for monitoring.

    Args:
        vector_store_config: Vector store configuration to modify in-place
    """
    bedrock_config = vector_store_config.bedrockKnowledgeBaseConfig
    if not bedrock_config:
        return

    datasource_bucket = bedrock_config.bedrockKnowledgeDatasourceS3Bucket

    default_pipeline = PipelineConfig(
        s3Bucket=datasource_bucket,
        s3Prefix="",
        trigger=PipelineTrigger.EVENT,
        autoRemove=True,
        chunkSize=1000,
        chunkOverlap=0,
    )

    if vector_store_config.pipelines:
        vector_store_config.pipelines.append(default_pipeline)
    else:
        vector_store_config.pipelines = [default_pipeline]
    logger.info(f"Auto-added default pipeline for Bedrock KB repository {vector_store_config.repositoryId}")
