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

"""Abstract base class for RAG evaluators."""

from abc import ABC, abstractmethod

from .metrics import ndcg_at_k, precision_at_k, recall_at_k
from .types import EvalResult, GoldenDatasetEntry, QueryResult


class BaseEvaluator(ABC):
    """Base class for RAG retrieval evaluators.

    Subclasses implement ``_retrieve()`` to fetch results from a specific
    backend.  The shared ``evaluate()`` method handles the golden-dataset
    loop, metric computation, and result assembly.

    Args:
        source_map: Mapping of short document names to full source URIs.
        k: Number of top results to evaluate.
    """

    def __init__(self, source_map: dict[str, str], k: int = 5) -> None:
        self.source_map = source_map
        self.k = k

    @abstractmethod
    def _retrieve(self, query: str) -> list[str]:
        """Return raw retrieved source URIs for a query."""

    def evaluate(self, golden: list[GoldenDatasetEntry]) -> EvalResult:
        """Run evaluation across all golden dataset entries.

        Args:
            golden: List of golden dataset entries to evaluate against.

        Returns:
            EvalResult with aggregate and per-query metrics.

        Raises:
            ValueError: If golden is empty or references unknown documents.
        """
        if not golden:
            raise ValueError("Golden dataset must not be empty.")

        all_p, all_r, all_n = [], [], []
        per_query: list[QueryResult] = []

        for entry in golden:
            retrieved = self._retrieve(entry.query)

            for doc in entry.expected:
                if doc not in self.source_map:
                    raise ValueError(
                        f"Golden dataset references unknown document '{doc}'. Available: {sorted(self.source_map)}"
                    )
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
                    query_type=entry.type,
                    precision=p,
                    recall=r_,
                    ndcg=n,
                    retrieved_files=[s.split("/")[-1] for s in retrieved],
                    expected_files=[self.source_map[doc].split("/")[-1] for doc in entry.expected],
                )
            )

        return EvalResult(
            precision=sum(all_p) / len(all_p),
            recall=sum(all_r) / len(all_r),
            ndcg=sum(all_n) / len(all_n),
            per_query=per_query,
        )
