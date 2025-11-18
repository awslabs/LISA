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

"""Base implementation for vector store-based repository services (OpenSearch, PGVector).

This class provides common functionality for repositories that use traditional
vector stores with chunking and embedding pipelines.
"""

import logging
import os
from abc import abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models.domain_objects import (
    CollectionMetadata,
    CollectionStatus,
    IngestionJob,
    RagCollectionConfig,
    RagDocument,
    VectorStoreStatus,
)
from repository.embeddings import RagEmbeddings
from utilities.vector_store import get_vector_store_client

from .repository_service import RepositoryService

logger = logging.getLogger(__name__)


class VectorStoreRepositoryService(RepositoryService):
    """Base implementation for vector store-based repository services.

    Provides common functionality for OpenSearch and PGVector repositories
    that share similar ingestion, deletion, and retrieval patterns.

    Subclasses only need to implement repository-specific operations like
    index/collection dropping and score normalization.
    """

    def supports_custom_collections(self) -> bool:
        """Vector stores support custom collections."""
        return True

    def should_create_default_collection(self) -> bool:
        """Vector stores create virtual default collections."""
        return True

    def get_collection_id_from_config(self, pipeline_config: Dict[str, Any]) -> str:
        """Extract collection ID from pipeline config or use embedding model."""
        collection_id = pipeline_config.get("collectionId")
        if not collection_id:
            collection_id = pipeline_config.get("embeddingModel")
        return collection_id

    def ingest_document(
        self,
        job: IngestionJob,
        texts: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> RagDocument:
        """Ingest document into vector store with chunking and embedding."""
        # Store chunks in vector store
        all_ids = self._store_chunks(
            texts=texts,
            metadatas=metadatas,
            collection_id=job.collection_id,
            embedding_model=job.embedding_model,
        )

        # Create document record
        rag_document = RagDocument(
            repository_id=job.repository_id,
            collection_id=job.collection_id,
            document_name=os.path.basename(job.s3_path),
            source=job.s3_path,
            subdocs=all_ids,
            chunk_strategy=job.chunk_strategy,
            username=job.username,
            ingestion_type=job.ingestion_type,
        )

        from repository.rag_document_repo import RagDocumentRepository

        rag_document_repository = RagDocumentRepository(
            os.environ["RAG_DOCUMENT_TABLE"], os.environ["RAG_SUB_DOCUMENT_TABLE"]
        )
        rag_document_repository.save(rag_document)

        logger.info(
            f"Ingested document {job.s3_path} ({len(all_ids)} chunks) "
            f"into {self.repository.get('type')} collection {job.collection_id}"
        )
        return rag_document

    def delete_document(
        self,
        document: RagDocument,
        s3_client: Any,
        bedrock_agent_client: Optional[Any] = None,
    ) -> None:
        """Delete document from vector store."""
        embeddings = RagEmbeddings(model_name=document.collection_id)
        vector_store = get_vector_store_client(
            document.repository_id,
            collection_id=document.collection_id,
            embeddings=embeddings,
        )
        vector_store.delete(document.subdocs)

    def delete_collection(
        self,
        collection_id: str,
        s3_client: Any,
        bedrock_agent_client: Optional[Any] = None,
    ) -> None:
        """Delete collection from vector store.

        Delegates to subclass-specific implementation for dropping
        indexes/collections.
        """
        self._drop_collection_index(collection_id)

    def retrieve_documents(
        self,
        query: str,
        collection_id: str,
        top_k: int,
        include_score: bool = False,
        bedrock_agent_client: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve documents from vector store using similarity search.

        Args:
            query: Search query
            collection_id: Collection to search
            top_k: Number of results to return
            include_score: Whether to include similarity scores in metadata
            bedrock_agent_client: Not used for vector stores

        Returns:
            List of documents with page_content and metadata
        """
        embeddings = RagEmbeddings(model_name=collection_id)
        vector_store = get_vector_store_client(
            self.repository_id,
            collection_id=collection_id,
            embeddings=embeddings,
        )

        results = vector_store.similarity_search_with_score(query, k=top_k)

        documents = []
        for i, (doc, score) in enumerate(results):
            doc_dict = {
                "page_content": doc.page_content,
                "metadata": doc.metadata.copy() if doc.metadata else {},
            }

            if include_score:
                # Normalize score based on repository type
                normalized_score = self._normalize_similarity_score(score)
                doc_dict["metadata"]["similarity_score"] = normalized_score

                logger.info(
                    f"Result {i + 1}: Raw Score={score:.4f}, Similarity={normalized_score:.4f}, "
                    f"Content: {doc.page_content[:200]}..."
                )
                logger.info(f"Result {i + 1} metadata: {doc.metadata}")

            documents.append(doc_dict)

        # Warn if all scores are low (possible embedding model mismatch)
        if include_score and results:
            max_score = max(self._normalize_similarity_score(score) for _, score in results)
            if max_score < 0.3:
                logger.warning(
                    f"All similarity scores < 0.3 for query '{query}' - " "possible embedding model mismatch"
                )

        return documents

    def validate_document_source(self, s3_path: str) -> str:
        """Vector stores accept any valid S3 path."""
        if not s3_path.startswith("s3://"):
            raise ValueError(f"Invalid S3 path: {s3_path}")
        return s3_path

    def get_vector_store_client(self, collection_id: str, embeddings: Any) -> Any:
        """Get vector store client for this repository."""
        return get_vector_store_client(
            self.repository_id,
            collection_id=collection_id,
            embeddings=embeddings,
        )

    # Protected methods for subclass customization

    @abstractmethod
    def _drop_collection_index(self, collection_id: str) -> None:
        """Drop collection index/table (repository-specific).

        Args:
            collection_id: Collection to drop
        """
        pass

    def _normalize_similarity_score(self, score: float) -> float:
        """Normalize similarity score to 0-1 range.

        Default implementation returns score as-is (for OpenSearch).
        Subclasses can override for different scoring systems (e.g., PGVector).

        Args:
            score: Raw similarity score from vector store

        Returns:
            Normalized score in 0-1 range
        """
        return score

    def create_default_collection(self) -> Optional[RagCollectionConfig]:
        """Create a default collection for vector store repositories.

        Returns:
            Default collection configuration using repository's embedding model
        """
        try:
            # Check if repository is active
            active = self.repository.get("status", VectorStoreStatus.UNKNOWN) in [
                VectorStoreStatus.CREATE_COMPLETE,
                VectorStoreStatus.UPDATE_COMPLETE,
                VectorStoreStatus.UPDATE_COMPLETE_CLEANUP_IN_PROGRESS,
                VectorStoreStatus.UPDATE_IN_PROGRESS,
            ]

            if not active:
                logger.info(f"Repository {self.repository_id} is not active")
                return None

            embedding_model = self.repository.get("embeddingModelId")
            if not embedding_model:
                logger.info(f"Repository {self.repository_id} has no default embedding model")
                return None

            # Use embedding model as collection ID
            collection_id = embedding_model
            sanitized_name = f"{self.repository.get('name', self.repository_id)}-{embedding_model}".replace(".", "-")

            default_collection = RagCollectionConfig(
                collectionId=collection_id,
                repositoryId=self.repository_id,
                name=sanitized_name,
                description="Default collection using repository's embedding model",
                embeddingModel=embedding_model,
                chunkingStrategy=self.repository.get("chunkingStrategy"),
                allowedGroups=self.repository.get("allowedGroups", []),
                createdBy=self.repository.get("createdBy", "system"),
                status=CollectionStatus.ACTIVE,
                metadata=CollectionMetadata(tags=["default"], customFields={}),
                allowChunkingOverride=True,
                pipelines=self.repository.get("pipelines", []),
                default=True,
                createdAt=datetime.now(timezone.utc),
                updatedAt=datetime.now(timezone.utc),
            )

            logger.info(f"Created virtual default collection for repository {self.repository_id}")
            return default_collection

        except Exception as e:
            logger.error(f"Failed to create default collection for repository {self.repository_id}: {e}")
            return None

    def _store_chunks(
        self,
        texts: List[str],
        metadatas: List[Dict[str, Any]],
        collection_id: str,
        embedding_model: str,
    ) -> List[str]:
        """Store document chunks in vector store."""
        embeddings = RagEmbeddings(model_name=embedding_model)
        vector_store = get_vector_store_client(
            self.repository_id,
            collection_id,
            embeddings,
        )

        all_ids = []
        batch_size = 500

        for i in range(0, len(texts), batch_size):
            text_batch = texts[i : i + batch_size]
            metadata_batch = metadatas[i : i + batch_size]

            batch_ids = vector_store.add_texts(texts=text_batch, metadatas=metadata_batch)

            if not batch_ids:
                raise Exception(f"Failed to store batch {i // batch_size + 1}")

            all_ids.extend(batch_ids)

        if not all_ids:
            raise Exception("Failed to store any documents in vector store")

        return all_ids
