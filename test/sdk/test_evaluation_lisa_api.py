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

"""Unit tests for LisaApiEvaluator."""

import pytest
import responses
from lisapy import LisaApi
from lisapy.evaluation import GoldenDatasetEntry, LisaApiEvaluator


def _make_similarity_result(source: str, content: str = "chunk text", score: float = 0.9) -> dict:
    """Build a single LISA API similarity_search result item."""
    return {
        "Document": {
            "page_content": content,
            "metadata": {"source": source},
        },
        "score": score,
    }


class TestLisaApiEvaluator:
    """Tests for LisaApiEvaluator with mocked HTTP responses."""

    @responses.activate
    def test_evaluate_single_query(self, lisa_api: LisaApi, api_url: str, source_map):
        responses.add(
            responses.GET,
            f"{api_url}/repository/test-repo/similaritySearch",
            json={
                "docs": [
                    _make_similarity_result("s3://bucket/doc_a.pdf"),
                    _make_similarity_result("s3://bucket/doc_b.pdf"),
                ]
            },
            status=200,
        )

        golden = [
            GoldenDatasetEntry(
                query="test query", expected=["doc_a", "doc_b"], relevance={"doc_a": 3, "doc_b": 1}, type="semantic"
            ),
        ]
        evaluator = LisaApiEvaluator(
            client=lisa_api, repo_id="test-repo", collection_id="default", source_map=source_map, k=5
        )
        result = evaluator.evaluate(golden)

        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.ndcg == pytest.approx(1.0)

    @responses.activate
    def test_evaluate_multiple_queries(self, lisa_api: LisaApi, api_url: str, source_map):
        # Query 1: match, Query 2: no match
        responses.add(
            responses.GET,
            f"{api_url}/repository/test-repo/similaritySearch",
            json={"docs": [_make_similarity_result("s3://bucket/doc_a.pdf")]},
            status=200,
        )
        responses.add(
            responses.GET,
            f"{api_url}/repository/test-repo/similaritySearch",
            json={"docs": [_make_similarity_result("s3://bucket/doc_c.pdf")]},
            status=200,
        )

        golden = [
            GoldenDatasetEntry(query="q1", expected=["doc_a"], relevance={"doc_a": 3}, type="semantic"),
            GoldenDatasetEntry(query="q2", expected=["doc_b"], relevance={"doc_b": 3}, type="semantic"),
        ]
        evaluator = LisaApiEvaluator(
            client=lisa_api, repo_id="test-repo", collection_id="default", source_map=source_map, k=5
        )
        result = evaluator.evaluate(golden)

        assert result.precision == pytest.approx(0.5)
        assert result.recall == pytest.approx(0.5)
        assert len(result.per_query) == 2

    @responses.activate
    def test_evaluate_negative_query(self, lisa_api: LisaApi, api_url: str, source_map):
        """Negative queries with empty expected should yield 0.0 metrics."""
        responses.add(
            responses.GET,
            f"{api_url}/repository/test-repo/similaritySearch",
            json={"docs": [_make_similarity_result("s3://bucket/doc_a.pdf")]},
            status=200,
        )

        golden = [
            GoldenDatasetEntry(query="irrelevant question", expected=[], relevance={}, type="negative"),
        ]
        evaluator = LisaApiEvaluator(
            client=lisa_api, repo_id="test-repo", collection_id="default", source_map=source_map, k=5
        )
        result = evaluator.evaluate(golden)

        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.ndcg == 0.0

    @responses.activate
    def test_deduplication_of_chunks(self, lisa_api: LisaApi, api_url: str, source_map):
        """Multiple chunks from same doc should be deduplicated."""
        responses.add(
            responses.GET,
            f"{api_url}/repository/test-repo/similaritySearch",
            json={
                "docs": [
                    _make_similarity_result("s3://bucket/doc_a.pdf", "chunk 1", 0.95),
                    _make_similarity_result("s3://bucket/doc_a.pdf", "chunk 2", 0.90),
                    _make_similarity_result("s3://bucket/doc_b.pdf", "chunk 3", 0.85),
                ]
            },
            status=200,
        )

        golden = [
            GoldenDatasetEntry(query="q1", expected=["doc_a"], relevance={"doc_a": 3}, type="semantic"),
        ]
        evaluator = LisaApiEvaluator(
            client=lisa_api, repo_id="test-repo", collection_id="default", source_map=source_map, k=5
        )
        result = evaluator.evaluate(golden)

        # After dedup: [doc_a, doc_b] → 1 hit / 2 unique = 0.5 precision
        assert result.precision == pytest.approx(0.5)
        assert result.recall == 1.0

    def test_evaluate_empty_golden_raises(self, lisa_api: LisaApi, source_map):
        """Passing an empty golden dataset should raise ValueError."""
        evaluator = LisaApiEvaluator(
            client=lisa_api, repo_id="test-repo", collection_id="default", source_map=source_map, k=5
        )
        with pytest.raises(ValueError, match="Golden dataset must not be empty"):
            evaluator.evaluate([])

    @responses.activate
    def test_evaluate_unknown_doc_in_expected_raises(self, lisa_api: LisaApi, api_url: str, source_map):
        """Unknown document key in expected should raise ValueError."""
        responses.add(
            responses.GET,
            f"{api_url}/repository/test-repo/similaritySearch",
            json={"docs": [_make_similarity_result("s3://bucket/doc_a.pdf")]},
            status=200,
        )

        golden = [
            GoldenDatasetEntry(query="q1", expected=["nonexistent"], relevance={"nonexistent": 3}, type="semantic"),
        ]
        evaluator = LisaApiEvaluator(
            client=lisa_api, repo_id="test-repo", collection_id="default", source_map=source_map, k=5
        )
        with pytest.raises(ValueError, match="unknown document 'nonexistent'"):
            evaluator.evaluate(golden)

    @responses.activate
    def test_http_401_propagates(self, lisa_api: LisaApi, api_url: str, source_map):
        """HTTP 401 should raise an exception, not be silently ignored."""
        responses.add(
            responses.GET,
            f"{api_url}/repository/test-repo/similaritySearch",
            json={"error": "Unauthorized"},
            status=401,
        )

        golden = [
            GoldenDatasetEntry(query="q1", expected=["doc_a"], relevance={"doc_a": 3}, type="semantic"),
        ]
        evaluator = LisaApiEvaluator(
            client=lisa_api, repo_id="test-repo", collection_id="default", source_map=source_map, k=5
        )
        with pytest.raises(Exception):
            evaluator.evaluate(golden)

    @responses.activate
    def test_http_500_propagates(self, lisa_api: LisaApi, api_url: str, source_map):
        """HTTP 500 should raise an exception."""
        responses.add(
            responses.GET,
            f"{api_url}/repository/test-repo/similaritySearch",
            json={"error": "Internal Server Error"},
            status=500,
        )

        golden = [
            GoldenDatasetEntry(query="q1", expected=["doc_a"], relevance={"doc_a": 3}, type="semantic"),
        ]
        evaluator = LisaApiEvaluator(
            client=lisa_api, repo_id="test-repo", collection_id="default", source_map=source_map, k=5
        )
        with pytest.raises(Exception):
            evaluator.evaluate(golden)

    @responses.activate
    def test_connection_error_propagates(self, lisa_api: LisaApi, api_url: str, source_map):
        """Connection errors should propagate."""
        responses.add(
            responses.GET,
            f"{api_url}/repository/test-repo/similaritySearch",
            body=ConnectionError("connection refused"),
        )

        golden = [
            GoldenDatasetEntry(query="q1", expected=["doc_a"], relevance={"doc_a": 3}, type="semantic"),
        ]
        evaluator = LisaApiEvaluator(
            client=lisa_api, repo_id="test-repo", collection_id="default", source_map=source_map, k=5
        )
        with pytest.raises(ConnectionError):
            evaluator.evaluate(golden)
