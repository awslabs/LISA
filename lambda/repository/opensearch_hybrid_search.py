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

"""OpenSearch hybrid search implementation for LISA."""
import logging
from typing import Any, Dict, List, Optional, Tuple

from langchain_community.vectorstores.opensearch_vector_search import OpenSearchVectorSearch
from langchain_core.documents import Document

logger = logging.getLogger(__name__)


class OpenSearchHybridSearch(OpenSearchVectorSearch):
    """OpenSearch vector store with hybrid search capabilities."""

    def _generate_search_pipeline(self, hybrid_weight: float) -> Dict[str, Any]:
        """Generate a search pipeline for hybrid search.

        Args:
            hybrid_weight: Weight for the kNN component (0-1)

        Returns:
            Dict containing the search pipeline configuration
        """
        # For backward compatibility
        base_search_pipeline = {
            "description": "Processor for hybrid search",
            "phase_results_processors": [
                {
                    "normalization-processor": {
                        "normalization": {"technique": "min_max"},
                        "combination": {
                            "technique": "arithmetic_mean",
                            "parameters": {"weights": [1 - hybrid_weight, hybrid_weight]},
                        },
                    }
                }
            ],
        }

        return base_search_pipeline

    def similarity_search_with_relevance_scores(
        self,
        query: str,
        k: int = 3,
        hybrid_weight: Optional[float] = None,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """Return documents most similar to query with relevance scores.

        If hybrid_weight is provided, uses hybrid search combining text and vector search.
        Otherwise, uses standard vector search.

        Args:
            query: Query text
            k: Number of documents to return
            hybrid_weight: Optional weight for the kNN component (0-1)

        Returns:
            List of documents with relevance scores
        """
        # If hybrid_weight is provided, use hybrid search
        if hybrid_weight is not None:
            return self._hybrid_search(query, k, hybrid_weight=hybrid_weight, **kwargs)

        # Otherwise, use the parent class's standard vector search
        return super().similarity_search_with_relevance_scores(query, k, **kwargs)

    def _hybrid_search(
        self,
        query: str,
        k: int = 3,
        hybrid_weight: float = 0.5,
        metadata_filters: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> List[Tuple[Document, float]]:
        """Perform hybrid search combining text and vector search.

        Args:
            query: Query text
            k: Number of documents to return
            hybrid_weight: Weight for the kNN component (0-1)
            metadata_filters: Optional list of metadata filters

        Returns:
            List of documents with relevance scores
        """

        metadata_queries = metadata_filters or []
        embed_query = self.embedding_function.embed_query(query)
        text_query = query
        size = k

        os_query = {
            "size": size,
            "query": {
                "hybrid": {
                    "queries": [
                        {
                            "bool": {
                                "filter": {"bool": {"must": metadata_queries}},
                                "must": {"match": {"text": text_query}},
                            }
                        },
                        {
                            "bool": {
                                "filter": {"bool": {"must": metadata_queries}},
                                "must": {"knn": {"vector_field": {"vector": embed_query, "k": size}}},
                            }
                        },
                    ]
                }
            },
            "search_pipeline": self._generate_search_pipeline(hybrid_weight),
        }

        response = self.client.search(
            index=self.index_name,
            body=os_query,
        )

        hits = list(response["hits"]["hits"])
        docs = []
        for hit in hits:
            source = hit["_source"]
            score = hit["_score"]
            text = source.get("text")
            metadata = {k: v for k, v in source.items() if k != "text"}
            docs.append((Document(page_content=text, metadata=metadata), score))

        return docs
