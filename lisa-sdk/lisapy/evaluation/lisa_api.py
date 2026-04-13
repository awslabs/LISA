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

from .metrics import ndcg_at_k, precision_at_k, recall_at_k
from .types import EvalResult, GoldenDatasetEntry, QueryResult


class LisaApiEvaluator:
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
        self.client = client
        self.repo_id = repo_id
        self.collection_id = collection_id
        self.source_map = source_map
        self.k = k

    def evaluate(self, golden: list[GoldenDatasetEntry]) -> EvalResult:
        """Run evaluation across all golden dataset entries.

        Args:
            golden: List of golden dataset entries to evaluate against.

        Returns:
            EvalResult with aggregate and per-query metrics.
        """
        all_p, all_r, all_n = [], [], []
        per_query: list[QueryResult] = []

        for entry in golden:
            results = self.client.similarity_search(
                repo_id=self.repo_id,
                query=entry.query,
                k=self.k,
                collection_id=self.collection_id,
            )
            retrieved = [r["Document"]["metadata"]["source"] for r in results]
            expected = {self.source_map[doc] for doc in entry.expected}
            rel_map = {self.source_map[doc]: entry.relevance[doc] for doc in entry.expected}

            p = precision_at_k(retrieved, expected, self.k)
            r_ = recall_at_k(retrieved, expected, self.k)
            n = ndcg_at_k(retrieved, rel_map, self.k)
            all_p.append(p)
            all_r.append(r_)
            all_n.append(n)

            per_query.append(
                QueryResult(
                    query=entry.query,
                    precision=p,
                    recall=r_,
                    ndcg=n,
                    retrieved_files=[s.split("/")[-1] for s in retrieved],
                    expected_files=[self.source_map[doc].split("/")[-1] for doc in entry.expected],
                )
            )

        return EvalResult(
            precision=sum(all_p) / len(all_p) if all_p else 0.0,
            recall=sum(all_r) / len(all_r) if all_r else 0.0,
            ndcg=sum(all_n) / len(all_n) if all_n else 0.0,
            per_query=per_query,
        )
