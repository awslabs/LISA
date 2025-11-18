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

"""Base service interface for repository operations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from models.domain_objects import IngestionJob, RagCollectionConfig, RagDocument


class RepositoryService(ABC):
    """Abstract base class defining repository-specific operations.

    Each repository type (OpenSearch, PGVector, Bedrock KB) implements this
    interface to provide type-specific behavior for document management.
    """

    def __init__(self, repository: Dict[str, Any]):
        """Initialize service with repository configuration.

        Args:
            repository: Repository configuration dictionary
        """
        self.repository = repository
        self.repository_id = repository.get("repositoryId")

    @abstractmethod
    def supports_custom_collections(self) -> bool:
        """Check if repository supports user-defined collections.

        Returns:
            True if custom collections are supported, False otherwise
        """
        pass

    @abstractmethod
    def should_create_default_collection(self) -> bool:
        """Check if a default/virtual collection should be created.

        Returns:
            True if default collection should be created, False otherwise
        """
        pass

    @abstractmethod
    def get_collection_id_from_config(self, pipeline_config: Dict[str, Any]) -> str:
        """Extract collection ID from pipeline configuration.

        Args:
            pipeline_config: Pipeline configuration dictionary

        Returns:
            Collection ID to use for operations
        """
        pass

    @abstractmethod
    def ingest_document(
        self,
        job: IngestionJob,
        texts: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> RagDocument:
        """Ingest a document into the repository.

        Args:
            job: Ingestion job with document details
            texts: List of text chunks
            metadatas: List of metadata dictionaries for each chunk

        Returns:
            RagDocument representing the ingested document
        """
        pass

    @abstractmethod
    def delete_document(
        self,
        document: RagDocument,
        s3_client: Any,
        bedrock_agent_client: Optional[Any] = None,
    ) -> None:
        """Delete a document from the repository.

        Args:
            document: Document to delete
            s3_client: S3 client for file operations
            bedrock_agent_client: Bedrock agent client (for Bedrock KB only)
        """
        pass

    @abstractmethod
    def delete_collection(
        self,
        collection_id: str,
        s3_client: Any,
        bedrock_agent_client: Optional[Any] = None,
    ) -> None:
        """Delete an entire collection from the repository.

        Args:
            collection_id: Collection to delete
            s3_client: S3 client for file operations
            bedrock_agent_client: Bedrock agent client (for Bedrock KB only)
        """
        pass

    @abstractmethod
    def retrieve_documents(
        self,
        query: str,
        collection_id: str,
        top_k: int,
        bedrock_agent_client: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieve documents matching a query.

        Args:
            query: Search query
            collection_id: Collection to search
            top_k: Number of results to return
            bedrock_agent_client: Bedrock agent client (for Bedrock KB only)

        Returns:
            List of matching documents with metadata
        """
        pass

    @abstractmethod
    def validate_document_source(self, s3_path: str) -> str:
        """Validate and normalize document source path.

        Args:
            s3_path: S3 path to validate

        Returns:
            Normalized S3 path

        Raises:
            ValueError: If path is invalid for this repository type
        """
        pass

    @abstractmethod
    def get_vector_store_client(self, collection_id: str, embeddings: Any) -> Optional[Any]:
        """Get vector store client for this repository.

        Args:
            collection_id: Collection identifier
            embeddings: Embeddings adapter

        Returns:
            Vector store client, or None if not applicable (e.g., Bedrock KB)
        """
        pass

    @abstractmethod
    def create_default_collection(self) -> Optional[RagCollectionConfig]:
        """Create a default collection for this repository.

        Returns:
            Default collection configuration, or None if not applicable
        """
        pass
