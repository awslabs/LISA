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

"""Unit tests for BedrockKBEvaluator."""

from unittest.mock import MagicMock, patch

import pytest
from lisapy.evaluation import BedrockKBEvaluator, GoldenDatasetEntry


def _make_retrieve_result(uri: str, score: float = 0.9) -> dict:
    """Build a single Bedrock KB retrieve() result item."""
    return {
        "content": {"text": f"Content from {uri}"},
        "location": {"s3Location": {"uri": uri}},
        "score": score,
    }


class TestBedrockKBEvaluator:
    """Tests for BedrockKBEvaluator with mocked boto3."""

    @patch("lisapy.evaluation.bedrock_kb.boto3.client")
    def test_evaluate_single_query(self, mock_boto_client, source_map):
        mock_kb = MagicMock()
        mock_boto_client.return_value = mock_kb
        mock_kb.retrieve.return_value = {
            "retrievalResults": [
                _make_retrieve_result("s3://bucket/doc_a.pdf", 0.95),
                _make_retrieve_result("s3://bucket/doc_b.pdf", 0.80),
            ]
        }

        golden = [
            GoldenDatasetEntry(
                query="test query", expected=["doc_a", "doc_b"], relevance={"doc_a": 3, "doc_b": 1}, type="semantic"
            ),
        ]
        evaluator = BedrockKBEvaluator(knowledge_base_id="KB123", source_map=source_map, region="us-east-1", k=5)
        result = evaluator.evaluate(golden)

        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.ndcg == pytest.approx(1.0)
        mock_kb.retrieve.assert_called_once()

    @patch("lisapy.evaluation.bedrock_kb.boto3.client")
    def test_evaluate_multiple_queries(self, mock_boto_client, source_map):
        mock_kb = MagicMock()
        mock_boto_client.return_value = mock_kb

        # Query 1: perfect match
        # Query 2: no match
        mock_kb.retrieve.side_effect = [
            {"retrievalResults": [_make_retrieve_result("s3://bucket/doc_a.pdf")]},
            {"retrievalResults": [_make_retrieve_result("s3://bucket/doc_c.pdf")]},
        ]

        golden = [
            GoldenDatasetEntry(query="q1", expected=["doc_a"], relevance={"doc_a": 3}, type="semantic"),
            GoldenDatasetEntry(query="q2", expected=["doc_b"], relevance={"doc_b": 3}, type="semantic"),
        ]
        evaluator = BedrockKBEvaluator(knowledge_base_id="KB123", source_map=source_map, region="us-east-1", k=5)
        result = evaluator.evaluate(golden)

        # Average of perfect (1.0) and zero (0.0)
        assert result.precision == pytest.approx(0.5)
        assert result.recall == pytest.approx(0.5)
        assert len(result.per_query) == 2

    @patch("lisapy.evaluation.bedrock_kb.boto3.client")
    def test_evaluate_zero_metrics_when_no_relevant_docs(self, mock_boto_client, source_map):
        """Metrics are 0.0 for both empty results and negative queries."""
        mock_kb = MagicMock()
        mock_boto_client.return_value = mock_kb
        mock_kb.retrieve.side_effect = [
            {"retrievalResults": []},
            {"retrievalResults": [_make_retrieve_result("s3://bucket/doc_a.pdf")]},
        ]

        golden = [
            GoldenDatasetEntry(query="q1", expected=["doc_a"], relevance={"doc_a": 3}, type="semantic"),
            GoldenDatasetEntry(query="irrelevant", expected=[], relevance={}, type="negative"),
        ]
        evaluator = BedrockKBEvaluator(knowledge_base_id="KB123", source_map=source_map, region="us-east-1", k=5)
        result = evaluator.evaluate(golden)

        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.ndcg == 0.0

    @patch("lisapy.evaluation.bedrock_kb.boto3.client")
    def test_deduplication_in_retrieve(self, mock_boto_client, source_map):
        """Multiple chunks from same doc should be deduplicated."""
        mock_kb = MagicMock()
        mock_boto_client.return_value = mock_kb
        mock_kb.retrieve.return_value = {
            "retrievalResults": [
                _make_retrieve_result("s3://bucket/doc_a.pdf", 0.95),
                _make_retrieve_result("s3://bucket/doc_a.pdf", 0.90),
                _make_retrieve_result("s3://bucket/doc_a.pdf", 0.85),
                _make_retrieve_result("s3://bucket/doc_b.pdf", 0.80),
                _make_retrieve_result("s3://bucket/doc_b.pdf", 0.75),
            ]
        }

        golden = [
            GoldenDatasetEntry(query="q1", expected=["doc_a"], relevance={"doc_a": 3}, type="semantic"),
        ]
        evaluator = BedrockKBEvaluator(knowledge_base_id="KB123", source_map=source_map, region="us-east-1", k=5)
        result = evaluator.evaluate(golden)

        # After dedup: [doc_a, doc_b] → 1 hit / 2 unique = 0.5 precision
        assert result.precision == pytest.approx(0.5)
        # Recall: 1 of 1 expected found = 1.0
        assert result.recall == 1.0

    @patch("lisapy.evaluation.bedrock_kb.boto3.client")
    def test_evaluate_empty_golden_raises(self, mock_boto_client, source_map):
        """Passing an empty golden dataset should raise ValueError."""
        evaluator = BedrockKBEvaluator(knowledge_base_id="KB123", source_map=source_map, region="us-east-1", k=5)
        with pytest.raises(ValueError, match="Golden dataset must not be empty"):
            evaluator.evaluate([])

    @patch("lisapy.evaluation.bedrock_kb.boto3.client")
    def test_evaluate_unknown_doc_in_expected_raises(self, mock_boto_client, source_map):
        """Unknown document key in expected should raise ValueError."""
        mock_kb = MagicMock()
        mock_boto_client.return_value = mock_kb
        mock_kb.retrieve.return_value = {"retrievalResults": [_make_retrieve_result("s3://bucket/doc_a.pdf")]}

        golden = [
            GoldenDatasetEntry(query="q1", expected=["nonexistent"], relevance={"nonexistent": 3}, type="semantic"),
        ]
        evaluator = BedrockKBEvaluator(knowledge_base_id="KB123", source_map=source_map, region="us-east-1", k=5)
        with pytest.raises(ValueError, match="unknown document 'nonexistent'"):
            evaluator.evaluate(golden)

    @patch("lisapy.evaluation.bedrock_kb.boto3.client")
    def test_boto3_client_error_propagates(self, mock_boto_client, source_map):
        """ClientError from retrieve() should propagate, not be swallowed."""
        from botocore.exceptions import ClientError

        mock_kb = MagicMock()
        mock_boto_client.return_value = mock_kb
        mock_kb.retrieve.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "denied"}}, "Retrieve"
        )

        golden = [
            GoldenDatasetEntry(query="q1", expected=["doc_a"], relevance={"doc_a": 3}, type="semantic"),
        ]
        evaluator = BedrockKBEvaluator(knowledge_base_id="KB123", source_map=source_map, region="us-east-1", k=5)
        with pytest.raises(ClientError):
            evaluator.evaluate(golden)
