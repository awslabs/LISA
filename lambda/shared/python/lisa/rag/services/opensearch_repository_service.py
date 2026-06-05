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
from lisa.domain.domain_objects import RetrieveResult
from lisa.rag.embeddings import RagEmbeddings
from lisa.utilities.common_functions import retry_config
from lisa.utilities.repository_types import RepositoryType
from opensearchpy import RequestsHttpConnection
from requests_aws4auth import AWS4Auth

from .vector_store_repository_service import VectorStoreRepositoryService

logger = logging.getLogger(__name__)
session = boto3.Session()
ssm_client = boto3.client("ssm", region_name=os.environ["AWS_REGION"], config=retry_config)


class OpenSearchRepositoryService(VectorStoreRepositoryService):
    """Service for OpenSearch repository operations.

    Inherits common vector store behavior from VectorStoreRepositoryService.
    Only implements OpenSearch-specific index management.
    """

    def supports_hybrid_search(self) -> bool:
        """OpenSearch >= 2.13 supports hybrid search via inline search pipelines.

        If the cluster is older than 2.13, hybrid_retrieve() will propagate the
        resulting RequestError — no silent fallback.
        """
        return True

    def hybrid_retrieve(
        self,
        query: str,
        collection_id: str,
        top_k: int,
        model_name: str,
        include_score: bool = False,
        bedrock_agent_client: Any = None,
        vector_weight: float = 0.7,
        lexical_weight: float = 0.3,
    ) -> RetrieveResult:
        """Retrieve documents using hybrid (BM25 + kNN) search via inline search pipeline.

        Sends the search pipeline definition inline in the request body — no persistent
        pipeline, no admin state, one round-trip. Requires OpenSearch 2.13+.

        Args:
            query: Search query text
            collection_id: Index/collection to search
            top_k: Number of results to return
            model_name: Embedding model name (used for query vector)
            include_score: When True, copies hit['_score'] (already 0-1 from min_max
                normalization) to metadata['similarity_score']
            bedrock_agent_client: Unused for OpenSearch (kept for base-class signature parity)
            vector_weight: Weight for vector (semantic) results (0-1)
            lexical_weight: Weight for lexical (keyword) results (0-1)

        Returns:
            RetrieveResult with actual_mode_used="hybrid" and hybrid_supported=True.
        """
        embeddings = RagEmbeddings(model_name=model_name)
        vector_store = self._get_vector_store_client(
            collection_id=collection_id,
            embeddings=embeddings,
        )

        if hasattr(vector_store, "client") and hasattr(vector_store.client, "indices"):
            if not vector_store.client.indices.exists(index=collection_id):
                logger.info(f"Collection {collection_id} does not exist. Returning empty docs.")
                return RetrieveResult(documents=[], actual_mode_used="hybrid", hybrid_supported=True)

        query_vector = embeddings.embed_query(query)
        body = self._build_hybrid_body(
            query=query,
            query_vector=query_vector,
            top_k=top_k,
            vector_weight=vector_weight,
            lexical_weight=lexical_weight,
        )

        logger.info(
            f"Hybrid retrieving from OpenSearch: collection={collection_id}, "
            f"weights=[{lexical_weight},{vector_weight}], query={query[:50]}..."
        )
        response = vector_store.client.search(index=collection_id, body=body)

        docs = self._extract_hits(response, include_score)
        return RetrieveResult(documents=docs, actual_mode_used="hybrid", hybrid_supported=True)

    @staticmethod
    def _build_hybrid_body(
        query: str,
        query_vector: list[float],
        top_k: int,
        vector_weight: float = 0.7,
        lexical_weight: float = 0.3,
    ) -> dict[str, Any]:
        """Construct the OpenSearch hybrid query + inline search_pipeline body.

        Built as a Python dict — no string interpolation — to prevent DSL injection (OWASP A03).
        OpenSearch weights order is [lexical, vector] matching the queries array order.
        """
        return {
            "size": top_k,
            "query": {
                "hybrid": {
                    "queries": [
                        {"match": {"text": {"query": query}}},
                        {"knn": {"vector_field": {"vector": query_vector, "k": top_k}}},
                    ]
                }
            },
            "search_pipeline": {
                "phase_results_processors": [
                    {
                        "normalization-processor": {
                            "normalization": {"technique": "min_max"},
                            "combination": {
                                "technique": "arithmetic_mean",
                                "parameters": {"weights": [lexical_weight, vector_weight]},
                            },
                        }
                    }
                ]
            },
        }

    @staticmethod
    def _extract_hits(response: dict[str, Any], include_score: bool) -> list[dict[str, Any]]:
        """Transform OpenSearch hits into the {page_content, metadata} doc shape."""
        documents: list[dict[str, Any]] = []
        for hit in response.get("hits", {}).get("hits", []):
            source = hit.get("_source", {})
            metadata = dict(source.get("metadata", {}) or {})
            if include_score:
                raw_score = hit.get("_score")
                if raw_score is not None:
                    metadata["similarity_score"] = float(raw_score)
            documents.append({"page_content": source.get("text", ""), "metadata": metadata})
        return documents

    def retrieve_documents(
        self,
        query: str,
        collection_id: str,
        top_k: int,
        model_name: str,
        include_score: bool = False,
        bedrock_agent_client: Any = None,
    ) -> RetrieveResult:
        """Retrieve documents from OpenSearch with index existence check.

        Args:
            query: Search query
            collection_id: Collection to search
            top_k: Number of results to return
            model_name: Embedding model name to use for query embedding
            include_score: Whether to include similarity scores in metadata
            bedrock_agent_client: Not used for OpenSearch

        Returns:
            RetrieveResult with actual_mode_used="vector" and hybrid_supported=True.
        """
        embeddings = RagEmbeddings(model_name=model_name)
        vector_store = self._get_vector_store_client(
            collection_id=collection_id,
            embeddings=embeddings,
        )

        if hasattr(vector_store, "client") and hasattr(vector_store.client, "indices"):
            if not vector_store.client.indices.exists(index=collection_id):
                logger.info(f"Collection {collection_id} does not exist. Returning empty docs.")
                return RetrieveResult(documents=[], actual_mode_used="vector", hybrid_supported=True)

        results = vector_store.similarity_search_with_score(query, k=top_k)

        documents = []
        for i, (doc, score) in enumerate(results):
            doc_dict = {
                "page_content": doc.page_content,
                "metadata": doc.metadata.copy() if doc.metadata else {},
            }

            if include_score:
                normalized_score = self._normalize_similarity_score(score)
                doc_dict["metadata"]["similarity_score"] = normalized_score

                logger.info(
                    f"Result {i + 1}: Raw Score={score:.4f}, Similarity={normalized_score:.4f}, "
                    f"Content: {doc.page_content[:200]}..."
                )
                logger.info(f"Result {i + 1} metadata: {doc.metadata}")

            documents.append(doc_dict)

        if include_score and results:
            max_score = max(self._normalize_similarity_score(score) for _, score in results)
            if max_score < 0.3:
                logger.warning(
                    f"All similarity scores < 0.3 for query '{query}' - " "possible embedding model mismatch"
                )

        return RetrieveResult(documents=documents, actual_mode_used="vector", hybrid_supported=True)

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
        if collection_id is not None:
            collection_id = collection_id.lower()

        return OpenSearchVectorSearch(
            opensearch_url=opensearch_endpoint,
            index_name=collection_id,
            embedding_function=embeddings,
            http_auth=auth,
            timeout=300,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection,
            engine="faiss",
        )
