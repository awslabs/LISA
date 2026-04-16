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

"""Evaluator for LISA API backends (OpenSearch, PGVector).

A single parameterized class covering any vector store backend
accessible via the LISA API's similarity_search endpoint.
"""

from lisapy.api import LisaApi

from .base import BaseEvaluator


class LisaApiEvaluator(BaseEvaluator):
    """Evaluate retrieval quality of a LISA API vector store backend.

    Works with any backend that supports similarity_search via the LISA API,
    including OpenSearch and PGVector repositories.

    Args:
        client: An authenticated LisaApi instance.
        repo_id: Repository identifier (e.g., "opensearch-test", "postgres-eval").
        collection_id: Collection identifier within the repository.
        source_map: Mapping of short document names to full S3 URIs.
        k: Number of top results to evaluate.
    """

    def __init__(
        self,
        client: LisaApi,
        repo_id: str,
        collection_id: str,
        source_map: dict[str, str],
        k: int = 5,
    ) -> None:
        super().__init__(source_map=source_map, k=k)
        self.client = client
        self.repo_id = repo_id
        self.collection_id = collection_id

    def _retrieve(self, query: str) -> list[str]:
        """Call LISA API similarity_search and return source URIs."""
        results = self.client.similarity_search(
            repo_id=self.repo_id,
            query=query,
            k=self.k,
            collection_id=self.collection_id,
        )
        return [r["Document"]["metadata"]["source"] for r in results]
