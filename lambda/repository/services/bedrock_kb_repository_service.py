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

"""Bedrock Knowledge Base repository service implementation."""

import logging
import os
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError
from models.domain_objects import (
    CollectionMetadata,
    CollectionStatus,
    IngestionJob,
    IngestionType,
    NoneChunkingStrategy,
    RagCollectionConfig,
    RagDocument,
)
from repository.rag_document_repo import RagDocumentRepository
from utilities.bedrock_kb import bulk_delete_documents_from_kb, delete_document_from_kb
from utilities.exceptions import HTTPException
from utilities.time import now, utc_now

from .repository_service import RepositoryService

logger = logging.getLogger(__name__)


class BedrockKBRepositoryService(RepositoryService):
    """Service for Bedrock Knowledge Base repository operations.

    Bedrock KB manages its own ingestion, chunking, and embedding pipeline.
    LISA only tracks documents and delegates actual operations to Bedrock.
    """

    def supports_custom_collections(self) -> bool:
        """Bedrock KB only supports default collections (data sources)."""
        return False

    def should_create_default_collection(self) -> bool:
        """Bedrock KB does not need virtual default collections."""
        return False

    def get_collection_id_from_config(self, pipeline_config: Dict[str, Any]) -> str:
        """For Bedrock KB, collection ID is the data source ID.

        Extracts the data source ID from the pipeline config's collectionId field,
        which should match one of the data sources in bedrockKnowledgeBaseConfig.
        """
        # The pipeline config should have a collectionId that matches a data source ID
        collection_id = pipeline_config.get("collectionId")

        if collection_id:
            return collection_id

        # Fallback: try to get from bedrock config (legacy support)
        bedrock_config = self.repository.get("bedrockKnowledgeBaseConfig", {})

        # Try new structure with dataSources array
        data_sources = bedrock_config.get("dataSources", [])
        if data_sources:
            first_data_source = data_sources[0]
            data_source_id = (
                first_data_source.get("id") if isinstance(first_data_source, dict) else first_data_source.id
            )
            return data_source_id

        # Try legacy single data source ID
        data_source_id = bedrock_config.get("bedrockKnowledgeDatasourceId")
        if data_source_id:
            return data_source_id

        raise ValueError(f"Bedrock KB repository {self.repository_id} missing data source ID")

    def ingest_document(
        self,
        job: IngestionJob,
        texts: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> RagDocument:
        """Track document for Bedrock KB - KB handles actual ingestion.

        Bedrock KB automatically ingests documents from its S3 data source.
        LISA only tracks the document metadata for querying and management.
        """
        bedrock_config = self.repository.get("bedrockKnowledgeBaseConfig", {})
        kb_bucket = bedrock_config.get("bedrockKnowledgeDatasourceS3Bucket")

        # Validate document is from KB bucket
        kb_s3_path = self._validate_and_normalize_path(job.s3_path, kb_bucket)

        # Check if document already tracked (idempotent)
        rag_document_repository = RagDocumentRepository(
            os.environ["RAG_DOCUMENT_TABLE"], os.environ["RAG_SUB_DOCUMENT_TABLE"]
        )

        existing_docs = list(
            rag_document_repository.find_by_source(job.repository_id, job.collection_id, kb_s3_path, join_docs=False)
        )

        if existing_docs:
            # Update existing document timestamp
            existing_doc = existing_docs[0]
            existing_doc.upload_date = now()
            rag_document_repository.save(existing_doc)
            logger.info(f"Document {kb_s3_path} already tracked, updated timestamp")
            return existing_doc

        # Create new document tracking entry
        rag_document = RagDocument(
            repository_id=job.repository_id,
            collection_id=job.collection_id,
            document_name=os.path.basename(kb_s3_path),
            source=kb_s3_path,
            subdocs=[],  # KB manages chunks internally
            chunk_strategy=NoneChunkingStrategy(),
            username=job.username,
            ingestion_type=job.ingestion_type,
        )
        rag_document_repository.save(rag_document)

        logger.info(f"Tracked document {kb_s3_path} for Bedrock KB. " f"KB will handle ingestion automatically.")
        return rag_document

    def delete_document(
        self,
        document: RagDocument,
        s3_client: Any,
        bedrock_agent_client: Optional[Any] = None,
    ) -> None:
        """Delete document from Bedrock KB."""
        if not bedrock_agent_client:
            raise ValueError("Bedrock agent client required for KB operations")

        # Create minimal job for deletion
        job = IngestionJob(
            repository_id=document.repository_id,
            collection_id=document.collection_id,
            s3_path=document.source,
            username=document.username,
            ingestion_type=document.ingestion_type,
        )

        delete_document_from_kb(
            s3_client=s3_client,
            bedrock_agent_client=bedrock_agent_client,
            job=job,
            repository=self.repository,
        )

    def delete_collection(
        self,
        collection_id: str,
        s3_client: Any,
        bedrock_agent_client: Optional[Any] = None,
    ) -> None:
        """Delete all LISA-managed documents from Bedrock KB collection.

        Only deletes documents with ingestion_type MANUAL or AUTO.
        Preserves user-managed documents (ingestion_type EXISTING).
        """
        if not bedrock_agent_client:
            raise ValueError("Bedrock agent client required for KB operations")

        dynamodb = boto3.resource("dynamodb")
        doc_table = dynamodb.Table(os.environ["RAG_DOCUMENT_TABLE"])

        pk = f"{self.repository_id}#{collection_id}"

        # Query all documents in collection
        response = doc_table.query(KeyConditionExpression=Key("pk").eq(pk))
        documents = response.get("Items", [])

        # Handle pagination
        while "LastEvaluatedKey" in response:
            response = doc_table.query(
                KeyConditionExpression=Key("pk").eq(pk), ExclusiveStartKey=response["LastEvaluatedKey"]
            )
            documents.extend(response.get("Items", []))

        logger.info(f"Found {len(documents)} total documents in collection")

        # Separate by ingestion type
        lisa_managed = [
            doc for doc in documents if doc.get("ingestion_type") in [IngestionType.MANUAL, IngestionType.AUTO]
        ]
        user_managed = [doc for doc in documents if doc.get("ingestion_type") == IngestionType.EXISTING]

        logger.info(
            f"Collection {collection_id}: " f"lisa_managed={len(lisa_managed)}, user_managed={len(user_managed)}"
        )

        # Extract S3 paths for LISA-managed documents
        s3_paths = [doc.get("source", "") for doc in lisa_managed if doc.get("source")]

        if s3_paths:
            bulk_delete_documents_from_kb(
                s3_client=s3_client,
                bedrock_agent_client=bedrock_agent_client,
                repository=self.repository,
                s3_paths=s3_paths,
                data_source_id=collection_id,
            )
            logger.info(
                f"Bulk deleted {len(s3_paths)} LISA-managed documents, "
                f"preserved {len(user_managed)} user-managed documents"
            )
        else:
            logger.info("No LISA-managed documents to delete from KB")

    def retrieve_documents(
        self,
        query: str,
        collection_id: str,
        top_k: int,
        model_name: str,
        include_score: bool = False,
        bedrock_agent_client: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve documents from Bedrock KB using retrieve API.

        Args:
            query: Search query
            collection_id: Collection to search (data source ID)
            top_k: Number of results to return
            model_name: Embedding model name (not used for Bedrock KB)
            include_score: Whether to include similarity scores in metadata
            bedrock_agent_client: Bedrock agent client for KB operations

        Returns:
            List of documents with page_content and metadata
        """
        if not bedrock_agent_client:
            raise ValueError("Bedrock agent client required for KB operations")

        bedrock_config = self.repository.get("bedrockKnowledgeBaseConfig", {})
        # Support both field names for backward compatibility
        kb_id = bedrock_config.get("knowledgeBaseId", bedrock_config.get("bedrockKnowledgeBaseId"))

        if not kb_id:
            raise ValueError(
                f"Bedrock KB repository '{self.repository_id}' is missing required field "
                f"'bedrockKnowledgeBaseId' or 'knowledgeBaseId' in bedrockKnowledgeBaseConfig. "
                f"Please update the repository configuration with the actual AWS Bedrock Knowledge Base ID "
                f"(e.g., 'KB123456' or a UUID format, not the LISA repository ID)."
            )

        # Use Bedrock retrieve API with data source filter
        logger.info(f"Retrieving from KB: kb_id={kb_id}, data_source={collection_id}, query={query[:50]}...")

        # Build retrieve params with data source filter
        retrieve_params = {
            "knowledgeBaseId": kb_id,
            "retrievalQuery": {"text": query},
            "retrievalConfiguration": {
                "vectorSearchConfiguration": {
                    "numberOfResults": top_k,
                }
            },
        }

        # Add data source filter if collection_id is provided
        # collection_id corresponds to the data source ID in Bedrock KB
        if collection_id:
            retrieve_params["retrievalConfiguration"]["vectorSearchConfiguration"]["filter"] = {
                "equals": {
                    "key": "x-amz-bedrock-kb-data-source-id",
                    "value": collection_id,
                }
            }
            logger.info(f"Filtering to data source: {collection_id}")

        try:
            response = bedrock_agent_client.retrieve(**retrieve_params)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            error_message = str(e)

            # Check for Aurora DB auto-pause error
            if error_code == "ValidationException" and "auto-paused" in error_message.lower():
                logger.warning(f"Aurora DB is resuming from auto-pause for KB {kb_id}")
                raise HTTPException(
                    status_code=503,
                    message=(
                        "The knowledge base database is currently starting up. "
                        "Please retry your request in a few moments."
                    ),
                )

            logger.error(f"Bedrock retrieve failed for KB {kb_id}: {error_message}")
            if "filter" in retrieve_params.get("retrievalConfiguration", {}).get("vectorSearchConfiguration", {}):
                logger.error(
                    "Filter may not be supported. Ensure metadata field 'x-amz-bedrock-kb-data-source-id' "
                    "is configured in the Knowledge Base."
                )
            raise
        except Exception as e:
            logger.error(f"Bedrock retrieve failed for KB {kb_id}: {str(e)}")
            raise

        # Transform Bedrock results to standard format
        documents = []
        for result in response.get("retrievalResults", []):
            metadata = result.get("metadata", {}).copy()

            # Add score to metadata if requested
            if include_score:
                metadata["similarity_score"] = result.get("score", 0.0)

            # Add location info to metadata
            location = result.get("location", {})
            if location:
                metadata["source"] = location.get("s3Location", {}).get("uri", "")

            documents.append(
                {
                    "page_content": result.get("content", {}).get("text", ""),
                    "metadata": metadata,
                }
            )

        return documents

    def validate_document_source(self, s3_path: str) -> str:
        """Validate document is from KB data source bucket."""
        bedrock_config = self.repository.get("bedrockKnowledgeBaseConfig", {})
        kb_bucket = bedrock_config.get("bedrockKnowledgeDatasourceS3Bucket")

        return self._validate_and_normalize_path(s3_path, kb_bucket)

    def get_vector_store_client(self, collection_id: str, embeddings: Any) -> Optional[Any]:
        """Bedrock KB does not use external vector store clients."""
        return None

    def _create_collection_for_data_source(
        self, data_source_id: str, s3_uri: str = "", is_default: bool = False, collection_name: Optional[str] = None
    ) -> RagCollectionConfig:
        """Create a collection configuration for a specific data source.

        Args:
            data_source_id: The data source ID to use as collection ID
            s3_uri: Optional S3 URI for the data source
            is_default: Whether this is the default collection
            collection_name: Optional collection name (defaults to data_source_id if not provided)

        Returns:
            Collection configuration for the data source
        """
        embedding_model = self.repository.get("embeddingModelId")
        # Use provided collection_name or fall back to data_source_id
        display_name = collection_name or f"{self.repository.get('name', self.repository_id)}-{data_source_id}"

        # Get KB name for description
        kb_name = self.repository.get("repositoryName") or self.repository.get("name", "Knowledge Base")

        # Set tags and description based on whether this is default
        if is_default:
            tags = ["default", "bedrock-kb"]
            description = f"Default collection for Bedrock Knowledge Base: {kb_name}"
        else:
            tags = ["bedrock-kb", "data-source"]
            description = f"Auto-created collection for {kb_name}"

        collection = RagCollectionConfig(
            collectionId=data_source_id,
            repositoryId=self.repository_id,
            name=display_name,
            description=description,
            embeddingModel=embedding_model,
            chunkingStrategy=None,  # KB controls chunking
            allowedGroups=self.repository.get("allowedGroups", []),
            createdBy=self.repository.get("createdBy", "system"),
            status=CollectionStatus.ACTIVE,
            metadata=CollectionMetadata(tags=tags, customFields={"s3Uri": s3_uri} if s3_uri else {}),
            allowChunkingOverride=False,  # KB controls chunking
            pipelines=self.repository.get("pipelines", []),
            default=is_default,
            dataSourceId=data_source_id,
            createdAt=utc_now(),
            updatedAt=utc_now(),
        )

        return collection

    def create_default_collection(self, ingest_docs=False) -> Optional[RagCollectionConfig]:
        """Create a default collection for Bedrock KB repository.

        For Bedrock KB, the collection ID is the data source ID.
        If multiple data sources exist, returns the first one.

        Returns:
            Default collection configuration for Bedrock KB
        """
        try:
            bedrock_config = self.repository.get("bedrockKnowledgeBaseConfig", {})

            # Handle new structure with dataSources array
            data_sources = bedrock_config.get("dataSources", [])

            # Also check for legacy single data source ID
            legacy_data_source_id = bedrock_config.get("bedrockKnowledgeDatasourceId")

            if not data_sources and not legacy_data_source_id:
                logger.warning(f"Bedrock KB repository {self.repository_id} missing data source ID")
                return None

            # Use first data source from array, or legacy single ID
            if data_sources:
                first_data_source = data_sources[0]
                data_source_id = (
                    first_data_source.get("id") if isinstance(first_data_source, dict) else first_data_source.id
                )
                s3_uri = (
                    first_data_source.get("s3Uri", "")
                    if isinstance(first_data_source, dict)
                    else getattr(first_data_source, "s3Uri", "")
                )
            else:
                data_source_id = legacy_data_source_id
                s3_uri = ""

            # Use helper method to create collection
            default_collection = self._create_collection_for_data_source(
                data_source_id=data_source_id, s3_uri=s3_uri, is_default=True
            )

            logger.info(f"Created virtual default collection for Bedrock KB repository {self.repository_id}")

            if ingest_docs:
                # Ingest existing documents from S3 bucket if s3pipeline is configured
                s3_bucket = bedrock_config.get("s3pipeline")

                if s3_bucket:
                    logger.info(
                        f"S3 pipeline configured with bucket {s3_bucket}. "
                        f"Document ingestion requires additional dependencies not available in this context."
                    )

            return default_collection

        except Exception as e:
            logger.error(f"Failed to create default collection for Bedrock KB repository {self.repository_id}: {e}")
            return None

    def _validate_and_normalize_path(self, s3_path: str, expected_bucket: str) -> str:
        """Validate S3 path is from expected bucket and normalize."""
        source_bucket = s3_path.split("/")[2] if s3_path.startswith("s3://") else None

        if source_bucket != expected_bucket:
            logger.warning(
                f"Document {s3_path} not from KB bucket {expected_bucket}. " f"Normalizing to KB bucket path."
            )
            # Normalize to KB bucket path
            return f"s3://{expected_bucket}/{os.path.basename(s3_path)}"

        return s3_path
