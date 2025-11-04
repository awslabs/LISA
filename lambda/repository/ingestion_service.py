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
from typing import Optional

import boto3
from models.domain_objects import Enum, IngestDocumentRequest, IngestionJob
from repository.collection_service import CollectionService

logger = logging.getLogger(__name__)

collection_server = CollectionService()


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
    ) -> IngestionJob:
        from models.domain_objects import FixedChunkingStrategy

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

        # Get metadata tags
        metadata = collection_server.get_collection_metadata(repository, collection, request.metadata)

        job = IngestionJob(
            repository_id=repository.get("repositoryId"),
            collection_id=collection_id,
            chunk_strategy=chunk_strategy,
            embedding_model=embedding_model,
            s3_path=s3_path,
            username=username,
            metadata=metadata,
        )
        logger.info(f"Created ingestion job with embedding_model: {embedding_model}")

        return job
