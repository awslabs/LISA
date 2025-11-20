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

"""OpenSearch repository service implementation."""

import json
import logging
import os
from typing import Any

import boto3
from langchain_community.vectorstores import OpenSearchVectorSearch
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
from opensearchpy import RequestsHttpConnection
from repository.embeddings import RagEmbeddings
from requests_aws4auth import AWS4Auth
from utilities.common_functions import retry_config
from utilities.repository_types import RepositoryType

from .vector_store_repository_service import VectorStoreRepositoryService

logger = logging.getLogger(__name__)
session = boto3.Session()
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)


class OpenSearchRepositoryService(VectorStoreRepositoryService):
    """Service for OpenSearch repository operations.

    Inherits common vector store behavior from VectorStoreRepositoryService.
    Only implements OpenSearch-specific index management.
    """

    def retrieve_documents(
        self,
        query: str,
        collection_id: str,
        top_k: int,
        model_name: str,
        include_score: bool = False,
        bedrock_agent_client: Any = None,
    ) -> list[dict[str, Any]]:
        """Retrieve documents from OpenSearch with index existence check.

        Args:
            query: Search query
            collection_id: Collection to search
            top_k: Number of results to return
            model_name: Embedding model name to use for query embedding
            include_score: Whether to include similarity scores in metadata
            bedrock_agent_client: Not used for OpenSearch

        Returns:
            List of documents with page_content and metadata
        """
        # Create embeddings and vector store client once
        embeddings = RagEmbeddings(model_name=model_name)
        vector_store = self._get_vector_store_client(
            collection_id=collection_id,
            embeddings=embeddings,
        )

        # Check if index exists before searching
        if hasattr(vector_store, "client") and hasattr(vector_store.client, "indices"):
            if not vector_store.client.indices.exists(index=collection_id):
                logger.info(f"Collection {collection_id} does not exist. Returning empty docs.")
                return []

        # Perform similarity search
        results = vector_store.similarity_search_with_score(query, k=top_k)

        documents = []
        for i, (doc, score) in enumerate(results):
            doc_dict = {
                "page_content": doc.page_content,
                "metadata": doc.metadata.copy() if doc.metadata else {},
            }

            if include_score:
                # OpenSearch scores are already normalized (0-1 range)
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

    def _drop_collection_index(self, collection_id: str) -> None:
        """Drop OpenSearch index for collection."""
        try:
            logger.info(f"Dropping OpenSearch index for collection {collection_id}")

            embeddings = RagEmbeddings(model_name=collection_id)
            vector_store = self._get_vector_store_client(
                collection_id=collection_id,
                embeddings=embeddings,
            )

            # Drop the index if it exists
            if hasattr(vector_store, "client") and hasattr(vector_store.client, "indices"):
                index_name = f"{self.repository_id}_{collection_id}".lower()
                if vector_store.client.indices.exists(index=index_name):
                    vector_store.client.indices.delete(index=index_name)
                    logger.info(f"Dropped OpenSearch index: {index_name}")
                else:
                    logger.info(f"OpenSearch index {index_name} does not exist")
            else:
                logger.warning("Vector store client does not support index operations")

        except Exception as e:
            logger.error(f"Failed to drop OpenSearch index: {e}", exc_info=True)
            # Don't raise - continue with document deletion

    # OpenSearch uses default score normalization (0-1 range already)

    def _get_vector_store_client(self, collection_id: str, embeddings: Embeddings) -> VectorStore:
        """Get OpenSearch vector store client.

        Args:
            collection_id: Collection identifier
            embeddings: Embeddings adapter

        Returns:
            OpenSearchVectorSearch client instance

        Raises:
            ValueError: If repository is not registered or not an OpenSearch repository
        """
        prefix = os.environ.get("REGISTERED_REPOSITORIES_PS_PREFIX")
        parameter_name = f"{prefix}{self.repository_id}"

        try:
            connection_info = ssm_client.get_parameter(Name=parameter_name)
            connection_info = json.loads(connection_info["Parameter"]["Value"])
        except ssm_client.exceptions.ParameterNotFound:
            logger.error(
                f"Repository '{self.repository_id}' not found in SSM Parameter Store. "
                f"Parameter: {parameter_name}. "
                f"Ensure the repository is registered before use."
            )
            raise ValueError(
                f"Repository '{self.repository_id}' is not registered. "
                f"Please register the repository before performing operations."
            )

        if not RepositoryType.is_type(connection_info, RepositoryType.OPENSEARCH):
            raise ValueError(f"Repository {self.repository_id} is not an OpenSearch repository")

        credentials = session.get_credentials()
        auth = AWS4Auth(
            credentials.access_key,
            credentials.secret_key,
            session.region_name,
            "es",
            session_token=credentials.token,
        )

        opensearch_endpoint = f"https://{connection_info.get('endpoint')}"

        return OpenSearchVectorSearch(
            opensearch_url=opensearch_endpoint,
            index_name=collection_id,
            embedding_function=embeddings,
            http_auth=auth,
            timeout=300,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
        )
