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

"""Unit tests for evaluation runner, format_report, and format_comparison."""

from unittest.mock import MagicMock, patch

import pytest
from lisapy.evaluation import (
    EvalConfig,
    format_comparison,
    format_report,
    GoldenDatasetEntry,
    run_evaluation,
)
from lisapy.evaluation.config import Backends, BedrockKBBackend, LisaApiBackend
from lisapy.evaluation.types import EvalResult, QueryResult


def _golden_dataset_jsonl(entries: list[GoldenDatasetEntry]) -> str:
    """Serialize golden dataset entries to JSONL string."""
    return "\n".join(e.model_dump_json() for e in entries)


GOLDEN = [
    GoldenDatasetEntry(query="test query", expected=["doc_a"], relevance={"doc_a": 3}, type="semantic"),
]


def _make_retrieve_result(uri: str, score: float = 0.9) -> dict:
    return {
        "content": {"text": f"Content from {uri}"},
        "location": {"s3Location": {"uri": uri}},
        "score": score,
    }


class TestRunEvaluation:
    """Tests for the run_evaluation orchestrator."""

    @patch("lisapy.evaluation.runner.BedrockKBEvaluator")
    def test_bedrock_only(self, mock_evaluator_cls, tmp_path):
        """Config with one Bedrock KB backend returns correct results."""
        mock_instance = MagicMock()
        mock_evaluator_cls.return_value = mock_instance
        mock_instance.evaluate.return_value = EvalResult(precision=0.8, recall=0.9, ndcg=0.85)

        dataset_file = tmp_path / "golden.jsonl"
        dataset_file.write_text(_golden_dataset_jsonl(GOLDEN))

        config = EvalConfig(
            region="us-east-1",
            k=5,
            documents={"doc_a": "a.pdf"},
            backends=Backends(
                bedrock_kb=[BedrockKBBackend(name="KB", knowledge_base_id="KB123", s3_bucket="s3://bucket")],
            ),
        )
        results = run_evaluation(config, str(dataset_file))
        assert "KB" in results
        assert results["KB"].precision == 0.8

    @patch("lisapy.evaluation.runner._create_lisa_client")
    def test_lisa_api_only(self, mock_create_client, tmp_path):
        """Config with one LISA API backend returns correct results."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_client.similarity_search.return_value = [
            {"Document": {"page_content": "text", "metadata": {"source": "s3://bucket/a.pdf"}}, "score": 0.9}
        ]

        dataset_file = tmp_path / "golden.jsonl"
        dataset_file.write_text(_golden_dataset_jsonl(GOLDEN))

        config = EvalConfig(
            region="us-east-1",
            k=5,
            documents={"doc_a": "a.pdf"},
            backends=Backends(
                lisa_api=[
                    LisaApiBackend(
                        name="OS",
                        api_url="https://api.example.com",
                        deployment_name="lisa-dev",
                        repo_id="test-repo",
                        s3_bucket="s3://bucket",
                    )
                ],
            ),
        )
        results = run_evaluation(config, str(dataset_file))
        assert "OS" in results
        assert results["OS"].recall == 1.0

    @patch("lisapy.evaluation.runner._create_lisa_client")
    def test_client_caching(self, mock_create_client, tmp_path):
        """Two LISA backends with same (api_url, deployment_name) share one client."""
        mock_client = MagicMock()
        mock_create_client.return_value = mock_client
        mock_client.similarity_search.return_value = [
            {"Document": {"page_content": "text", "metadata": {"source": "s3://bucket/a.pdf"}}, "score": 0.9}
        ]

        dataset_file = tmp_path / "golden.jsonl"
        dataset_file.write_text(_golden_dataset_jsonl(GOLDEN))

        shared_kwargs = {
            "api_url": "https://api.example.com",
            "deployment_name": "lisa-dev",
            "s3_bucket": "s3://bucket",
        }
        config = EvalConfig(
            region="us-east-1",
            k=5,
            documents={"doc_a": "a.pdf"},
            backends=Backends(
                lisa_api=[
                    LisaApiBackend(name="OS", repo_id="os-repo", **shared_kwargs),
                    LisaApiBackend(name="PG", repo_id="pg-repo", **shared_kwargs),
                ],
            ),
        )
        run_evaluation(config, str(dataset_file))
        mock_create_client.assert_called_once()

    @patch("lisapy.evaluation.runner.setup_authentication")
    def test_auth_failure_propagates(self, mock_auth, tmp_path):
        """RuntimeError from setup_authentication should propagate."""
        mock_auth.side_effect = RuntimeError("no credentials")

        dataset_file = tmp_path / "golden.jsonl"
        dataset_file.write_text(_golden_dataset_jsonl(GOLDEN))

        config = EvalConfig(
            region="us-east-1",
            k=5,
            documents={"doc_a": "a.pdf"},
            backends=Backends(
                lisa_api=[
                    LisaApiBackend(
                        name="OS",
                        api_url="https://api.example.com",
                        deployment_name="lisa-dev",
                        repo_id="test-repo",
                        s3_bucket="s3://bucket",
                    )
                ],
            ),
        )
        with pytest.raises(RuntimeError, match="no credentials"):
            run_evaluation(config, str(dataset_file))

    def test_empty_backends_returns_empty(self, tmp_path):
        """Config with no backends should return empty dict."""
        dataset_file = tmp_path / "golden.jsonl"
        dataset_file.write_text(_golden_dataset_jsonl(GOLDEN))

        config = EvalConfig(
            region="us-east-1",
            k=5,
            documents={"doc_a": "a.pdf"},
            backends=Backends(),
        )
        results = run_evaluation(config, str(dataset_file))
        assert results == {}

    @patch("lisapy.evaluation.runner.BedrockKBEvaluator")
    def test_no_stdout_pollution(self, mock_evaluator_cls, tmp_path, capsys):
        """run_evaluation should not print to stdout."""
        mock_instance = MagicMock()
        mock_evaluator_cls.return_value = mock_instance
        mock_instance.evaluate.return_value = EvalResult(precision=0.8, recall=0.9, ndcg=0.85)

        dataset_file = tmp_path / "golden.jsonl"
        dataset_file.write_text(_golden_dataset_jsonl(GOLDEN))

        config = EvalConfig(
            region="us-east-1",
            k=5,
            documents={"doc_a": "a.pdf"},
            backends=Backends(
                bedrock_kb=[BedrockKBBackend(name="KB", knowledge_base_id="KB123", s3_bucket="s3://bucket")],
            ),
        )
        run_evaluation(config, str(dataset_file))
        captured = capsys.readouterr()
        assert captured.out == ""


class TestFormatReport:
    """Tests for format_report string output."""

    def test_report_contains_metrics(self):
        result = EvalResult(
            precision=0.8,
            recall=0.9,
            ndcg=0.85,
            per_query=[
                QueryResult(
                    query="test query",
                    precision=0.8,
                    recall=0.9,
                    ndcg=0.85,
                    retrieved_files=["a.pdf"],
                    expected_files=["a.pdf"],
                )
            ],
        )
        golden = [GoldenDatasetEntry(query="test query", expected=["doc_a"], relevance={"doc_a": 3}, type="semantic")]
        report = format_report("TestBackend", result, golden, k=5)
        assert "TestBackend" in report
        assert "0.800" in report
        assert "0.900" in report
        assert "0.850" in report

    def test_report_no_crash_on_empty_per_query(self):
        """Report should not crash with empty per_query (edge case)."""
        result = EvalResult(precision=0.0, recall=0.0, ndcg=0.0)
        report = format_report("Empty", result, [], k=5)
        assert "Empty" in report


class TestFormatComparison:
    """Tests for format_comparison string output."""

    def test_comparison_contains_backend_names(self):
        results = {
            "KB": EvalResult(precision=0.8, recall=0.9, ndcg=0.85),
            "OS": EvalResult(precision=0.7, recall=0.8, ndcg=0.75),
        }
        output = format_comparison(results, k=5)
        assert "KB" in output
        assert "OS" in output
        assert "Cross-Backend Comparison" in output
        assert "Pairwise Deltas" in output
