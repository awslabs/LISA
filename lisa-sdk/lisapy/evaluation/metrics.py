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

"""Information retrieval metrics for RAG evaluation.

Pure functions with no external dependencies — safe to use without AWS credentials.
"""

import math


def deduplicate_sources(sources: list[str]) -> list[str]:
    """Deduplicate source paths preserving first-occurrence rank order.

    RAG retrieval returns multiple chunks per document. For document-level evaluation, we only care about the rank of
    the first chunk from each unique source document.
    """
    seen: set[str] = set()
    deduped: list[str] = []
    for s in sources:
        if s not in seen:
            seen.add(s)
            deduped.append(s)
    return deduped


def precision_at_k(retrieved_sources: list[str], expected_sources: set[str], k: int) -> float:
    """Of the top-k unique documents retrieved, what fraction are relevant?"""
    deduped = deduplicate_sources(retrieved_sources)[:k]
    if not deduped:
        return 0.0
    hits = sum(1 for s in deduped if s in expected_sources)
    return hits / len(deduped)


def recall_at_k(retrieved_sources: list[str], expected_sources: set[str], k: int) -> float:
    """Of all expected documents, what fraction were found in top-k results?"""
    deduped = deduplicate_sources(retrieved_sources)[:k]
    if not expected_sources:
        return 0.0
    hits = sum(1 for s in deduped if s in expected_sources)
    return hits / len(expected_sources)


def ndcg_at_k(retrieved_sources: list[str], relevance_map: dict[str, int], k: int) -> float:
    """Position-weighted graded relevance over unique documents.

    Uses rank of first chunk from each unique source document.
    Score range: 0.0 (no relevant docs) to 1.0 (perfect ranking).
    """
    deduped = deduplicate_sources(retrieved_sources)[:k]
    dcg = sum((2 ** relevance_map.get(s, 0) - 1) / math.log2(i + 2) for i, s in enumerate(deduped))
    ideal = sorted(relevance_map.values(), reverse=True)
    idcg = sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(ideal[:k]))
    return dcg / idcg if idcg > 0 else 0.0
