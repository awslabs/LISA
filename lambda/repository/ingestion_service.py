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
from typing import Any, Dict, Optional

import boto3
from models.domain_objects import Enum, FixedChunkingStrategy, IngestDocumentRequest, IngestionJob, IngestionType
from repository.metadata_generator import MetadataGenerator

logger = logging.getLogger(__name__)


class IngestionAction(str, Enum):
    Ingest = "ingest"
    Delete = "delete"


class DocumentIngestionService:
    def _submit_job(self, job: IngestionJob, action: IngestionAction) -> None:
        # Submit AWS Batch job
        batch_client = boto3.client("batch", region_name=os.environ["AWS_REGION"])
        response = batch_client.submit_job(
            jobName=f"document-{action.value}-{job.id}",
            jobQueue=os.environ["LISA_INGESTION_JOB_QUEUE_NAME"],
            jobDefinition=os.environ["LISA_INGESTION_JOB_DEFINITION_NAME"],
            parameters={"DOCUMENT_ID": job.id, "ACTION": action},
        )
        logger.info(f"Submitted {action} job for document {job.id}: {response['jobId']}")

    def submit_create_job(self, job: IngestionJob) -> None:
        self._submit_job(job, IngestionAction("ingest"))

    def create_delete_job(self, job: IngestionJob) -> None:
        self._submit_job(job, IngestionAction("delete"))

    def create_ingestion_job(
        self,
        repository: dict,
        collection: Optional[dict],
        request: IngestDocumentRequest,
        query_params: dict,
        s3_path: str,
        username: str,
        metadata: Optional[Dict[str, Any]] = None,
        ingestion_type: IngestionType = IngestionType.MANUAL,
    ) -> IngestionJob:

        # Determine collection_id
        collection_id = (
            request.collectionId
            or (request.embeddingModel.get("modelName") if request.embeddingModel else None)
            or repository.get("embeddingModelId")
        )

        # Determine chunking strategy
        chunk_strategy = None
        if collection and request.chunkingStrategy and collection.get("allowChunkingOverride"):
            try:
                chunk_strategy = (
                    FixedChunkingStrategy(**request.chunkingStrategy)
                    if request.chunkingStrategy.get("type", "").upper() == "FIXED"
                    else collection.get("chunkingStrategy")
                )
            except Exception:
                chunk_strategy = collection.get("chunkingStrategy")
        elif collection:
            chunk_strategy = collection.get("chunkingStrategy")
        if not chunk_strategy:
            chunk_strategy = FixedChunkingStrategy(
                size=str(query_params.get("chunkSize", 1000)),
                overlap=str(query_params.get("chunkOverlap", 200)),
            )

        # Get embedding model
        embedding_model = collection.get("embeddingModel") if collection else repository.get("embeddingModelId")
        source = "collection" if collection else "repository"
        logger.info(f"Using embedding model for ingestion: {embedding_model} (from {source})")

        # Merge metadata from repository, collection, and document sources
        merged_metadata = MetadataGenerator.merge_metadata(
            repository=repository,
            collection=collection,
            document_metadata=metadata,
            for_bedrock_kb=False,  # Keep tags as array for ingestion jobs
        )

        job = IngestionJob(
            repository_id=repository.get("repositoryId"),
            collection_id=collection_id,
            chunk_strategy=chunk_strategy,
            embedding_model=embedding_model,
            s3_path=s3_path,
            username=username,
            metadata=merged_metadata,
            ingestion_type=ingestion_type,
        )
        logger.info(f"Created ingestion job with embedding_model: {embedding_model}")

        return job

    def _merge_metadata_for_ingestion(
        self,
        repository: dict,
        collection: Optional[dict],
        document_metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Merge metadata from repository, collection, and document sources for ingestion jobs.

        This ensures the ingestion job contains the complete merged metadata that will be
        applied to documents during ingestion, following the hierarchy:
        1. Repository metadata (lowest precedence)
        2. Collection metadata (medium precedence)
        3. Document metadata (highest precedence)

        Args:
            repository: Repository configuration dictionary
            collection: Collection configuration dictionary (optional)
            document_metadata: Document-specific metadata (optional)

        Returns:
            Merged metadata dictionary or None if no metadata sources exist
        """
        merged_metadata: Dict[str, Any] = {}

        # 1. Merge repository metadata (lowest precedence)
        repo_metadata = repository.get("metadata")
        if repo_metadata:
            if isinstance(repo_metadata, dict):
                # Add repository tags
                repo_tags = repo_metadata.get("tags", [])
                if repo_tags:
                    merged_metadata["tags"] = repo_tags.copy()
                # Add other repository metadata
                for key, value in repo_metadata.items():
                    if key != "tags":
                        merged_metadata[key] = value
            elif hasattr(repo_metadata, "tags"):
                # Handle metadata objects with tags attribute
                if repo_metadata.tags:
                    merged_metadata["tags"] = list(repo_metadata.tags)

        # 2. Merge collection metadata (medium precedence)
        if collection and collection.get("metadata"):
            coll_metadata = collection["metadata"]
            if isinstance(coll_metadata, dict):
                # Merge collection tags with repository tags
                coll_tags = coll_metadata.get("tags", [])
                if coll_tags:
                    existing_tags = merged_metadata.get("tags", [])
                    # Combine tags, with collection tags taking precedence for duplicates
                    all_tags = existing_tags + [tag for tag in coll_tags if tag not in existing_tags]
                    merged_metadata["tags"] = all_tags
                # Add other collection metadata
                for key, value in coll_metadata.items():
                    if key != "tags":
                        merged_metadata[key] = value
            elif hasattr(coll_metadata, "tags"):
                # Handle metadata objects with tags attribute
                if coll_metadata.tags:
                    existing_tags = merged_metadata.get("tags", [])
                    all_tags = existing_tags + [tag for tag in coll_metadata.tags if tag not in existing_tags]
                    merged_metadata["tags"] = all_tags

        # 3. Merge document metadata (highest precedence)
        if document_metadata:
            # Document metadata completely overrides any conflicting keys
            for key, value in document_metadata.items():
                if key == "tags" and isinstance(value, list):
                    # For tags, merge with existing tags, document tags take precedence
                    existing_tags = merged_metadata.get("tags", [])
                    all_tags = existing_tags + [tag for tag in value if tag not in existing_tags]
                    merged_metadata["tags"] = all_tags
                else:
                    merged_metadata[key] = value

        # Add repository and collection identifiers for traceability
        merged_metadata["repositoryId"] = repository.get("repositoryId", "")
        merged_metadata["collectionId"] = collection.get("collectionId", "") if collection else "default"

        logger.info(f"Merged metadata for ingestion job: {merged_metadata}")

        return merged_metadata if merged_metadata else None
