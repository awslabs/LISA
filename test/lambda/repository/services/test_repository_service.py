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

"""Tests for repository service base class."""

import os
from typing import Any, Dict, List, Optional

import pytest

# Set required environment variables BEFORE any imports
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("RAG_DOCUMENT_TABLE", "test-doc-table")
os.environ.setdefault("RAG_SUB_DOCUMENT_TABLE", "test-subdoc-table")

from models.domain_objects import IngestionJob, RagCollectionConfig, RagDocument
from repository.services.repository_service import RepositoryService


class ConcreteRepositoryService(RepositoryService):
    """Concrete implementation for testing abstract base class."""

    def supports_custom_collections(self) -> bool:
        return True

    def should_create_default_collection(self) -> bool:
        return True

    def get_collection_id_from_config(self, pipeline_config: Dict[str, Any]) -> str:
        return pipeline_config.get("collectionId", "default-collection")

    def ingest_document(
        self,
        job: IngestionJob,
        texts: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> RagDocument:
        return RagDocument(
            repository_id=job.repository_id,
            collection_id=job.collection_id,
            document_name="test.pdf",
            source=job.s3_path,
            subdocs=[],
            chunk_strategy=job.chunk_strategy,
            username=job.username,
            ingestion_type=job.ingestion_type,
        )

    def delete_document(
        self,
        document: RagDocument,
        s3_client: Any,
        bedrock_agent_client: Optional[Any] = None,
    ) -> None:
        pass

    def delete_collection(
        self,
        collection_id: str,
        s3_client: Any,
        bedrock_agent_client: Optional[Any] = None,
    ) -> None:
        pass

    def retrieve_documents(
        self,
        query: str,
        collection_id: str,
        top_k: int,
        bedrock_agent_client: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        return []

    def validate_document_source(self, s3_path: str) -> str:
        return s3_path

    def get_vector_store_client(self, collection_id: str, embeddings: Any) -> Optional[Any]:
        return None

    def create_default_collection(self) -> Optional[RagCollectionConfig]:
        return None


class TestRepositoryService:
    """Test suite for RepositoryService base class."""

    def test_initialization(self):
        """Test service initialization with repository config."""
        repository = {"repositoryId": "test-repo", "type": "opensearch", "name": "Test Repository"}

        service = ConcreteRepositoryService(repository)

        assert service.repository == repository
        assert service.repository_id == "test-repo"

    def test_initialization_missing_repository_id(self):
        """Test service initialization without repository ID."""
        repository = {"type": "opensearch", "name": "Test Repository"}

        service = ConcreteRepositoryService(repository)

        assert service.repository == repository
        assert service.repository_id is None

    def test_abstract_methods_must_be_implemented(self):
        """Test that abstract methods must be implemented by subclasses."""
        # Attempting to instantiate RepositoryService directly should fail
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            RepositoryService({"repositoryId": "test"})

    def test_concrete_implementation_methods(self):
        """Test that concrete implementation provides all required methods."""
        repository = {"repositoryId": "test-repo"}
        service = ConcreteRepositoryService(repository)

        # Test all abstract methods are implemented
        assert service.supports_custom_collections() is True
        assert service.should_create_default_collection() is True
        assert service.get_collection_id_from_config({}) == "default-collection"
        assert service.validate_document_source("s3://bucket/file") == "s3://bucket/file"
        assert service.get_vector_store_client("col", None) is None
        assert service.create_default_collection() is None
        assert service.retrieve_documents("query", "col", 5) == []
