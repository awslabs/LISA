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

"""Unit tests for RAG evaluation metric functions."""

import pytest
from lisapy.evaluation import deduplicate_sources, ndcg_at_k, precision_at_k, recall_at_k


class TestDeduplicateSources:
    """Tests for deduplicate_sources() — preserves first-occurrence rank order."""

    def test_removes_duplicates_preserving_rank_order(self):
        assert deduplicate_sources(["c", "a", "b", "a", "c"]) == ["c", "a", "b"]

    def test_empty_list(self):
        assert deduplicate_sources([]) == []

    def test_all_same(self):
        assert deduplicate_sources(["a", "a", "a"]) == ["a"]


class TestPrecisionAtK:
    """Tests for precision_at_k() — fraction of top-k unique docs that are relevant."""

    def test_perfect_precision(self):
        retrieved = ["s3://a.pdf", "s3://b.pdf"]
        expected = {"s3://a.pdf", "s3://b.pdf"}
        assert precision_at_k(retrieved, expected, k=5) == 1.0

    def test_zero_precision(self):
        retrieved = ["s3://x.pdf", "s3://y.pdf"]
        expected = {"s3://a.pdf", "s3://b.pdf"}
        assert precision_at_k(retrieved, expected, k=5) == 0.0

    def test_partial_precision(self):
        retrieved = ["s3://a.pdf", "s3://x.pdf", "s3://y.pdf", "s3://z.pdf", "s3://b.pdf"]
        expected = {"s3://a.pdf", "s3://b.pdf"}
        assert precision_at_k(retrieved, expected, k=5) == pytest.approx(2 / 5)

    def test_empty_retrieved(self):
        assert precision_at_k([], {"s3://a.pdf"}, k=5) == 0.0

    def test_k_truncation(self):
        retrieved = ["s3://a.pdf", "s3://b.pdf", "s3://c.pdf", "s3://d.pdf"]
        expected = {"s3://c.pdf", "s3://d.pdf"}
        # k=2 → only [a, b] considered → 0 hits
        assert precision_at_k(retrieved, expected, k=2) == 0.0


class TestRecallAtK:
    """Tests for recall_at_k() — fraction of expected docs found in top-k."""

    def test_perfect_recall(self):
        retrieved = ["s3://a.pdf", "s3://b.pdf", "s3://x.pdf"]
        expected = {"s3://a.pdf", "s3://b.pdf"}
        assert recall_at_k(retrieved, expected, k=5) == 1.0

    def test_zero_recall(self):
        retrieved = ["s3://x.pdf", "s3://y.pdf"]
        expected = {"s3://a.pdf", "s3://b.pdf"}
        assert recall_at_k(retrieved, expected, k=5) == 0.0

    def test_partial_recall(self):
        retrieved = ["s3://a.pdf", "s3://x.pdf"]
        expected = {"s3://a.pdf", "s3://b.pdf"}
        assert recall_at_k(retrieved, expected, k=5) == pytest.approx(0.5)

    def test_empty_expected(self):
        assert recall_at_k(["s3://a.pdf"], set(), k=5) == 0.0

    def test_empty_retrieved(self):
        assert recall_at_k([], {"s3://a.pdf"}, k=5) == 0.0


class TestNdcgAtK:
    """Tests for ndcg_at_k() — position-weighted graded relevance."""

    def test_perfect_ndcg(self):
        # Most relevant doc at rank 1, less relevant at rank 2
        retrieved = ["s3://a.pdf", "s3://b.pdf"]
        relevance = {"s3://a.pdf": 3, "s3://b.pdf": 1}
        assert ndcg_at_k(retrieved, relevance, k=5) == pytest.approx(1.0)

    def test_zero_ndcg(self):
        retrieved = ["s3://x.pdf", "s3://y.pdf"]
        relevance = {"s3://a.pdf": 3}
        assert ndcg_at_k(retrieved, relevance, k=5) == pytest.approx(0.0)

    def test_imperfect_ranking(self):
        # Less relevant doc at rank 1, more relevant at rank 2
        retrieved = ["s3://b.pdf", "s3://a.pdf"]
        relevance = {"s3://a.pdf": 3, "s3://b.pdf": 1}
        result = ndcg_at_k(retrieved, relevance, k=5)
        assert 0.0 < result < 1.0

    def test_empty_relevance_map(self):
        retrieved = ["s3://a.pdf", "s3://b.pdf"]
        assert ndcg_at_k(retrieved, {}, k=5) == 0.0

    def test_k_limits_evaluation(self):
        # 3 relevant docs, but k=1 — only first position counts
        retrieved = ["s3://x.pdf", "s3://a.pdf", "s3://b.pdf"]
        relevance = {"s3://a.pdf": 3, "s3://b.pdf": 2}
        result_k1 = ndcg_at_k(retrieved, relevance, k=1)
        result_k3 = ndcg_at_k(retrieved, relevance, k=3)
        # k=1 only sees irrelevant doc → 0.0
        assert result_k1 == pytest.approx(0.0)
        # k=3 sees both relevant docs → positive
        assert result_k3 > 0.0
