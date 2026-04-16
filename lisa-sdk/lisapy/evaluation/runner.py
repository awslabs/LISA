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

"""Evaluation runner — orchestrates evaluation across all configured backends."""

import logging

from lisapy.api import LisaApi
from lisapy.authentication import setup_authentication

from .bedrock_kb import BedrockKBEvaluator
from .config import EvalConfig, LisaApiBackend
from .dataset import load_golden_dataset
from .lisa_api import LisaApiEvaluator
from .types import EvalResult, GoldenDatasetEntry

logger = logging.getLogger(__name__)


def _create_lisa_client(backend: LisaApiBackend, region: str) -> LisaApi:
    """Create an authenticated LISA API client for a backend.

    Fetches the management key from AWS Secrets Manager and registers
    it in DynamoDB for token-based auth via :func:`lisapy.authentication.setup_authentication`.
    """
    headers = setup_authentication(backend.deployment_name, region=region)
    return LisaApi(url=backend.api_url, headers=headers, verify=True, timeout=10)


def _fmt_delta(v: float) -> str:
    """Format a metric delta with sign prefix."""
    return f"{'+' if v > 0 else ''}{v:.3f}"


def format_report(name: str, result: EvalResult, golden: list[GoldenDatasetEntry], k: int) -> str:
    """Format evaluation results with breakdown by query type.

    Returns:
        Formatted multi-line report string.
    """
    lines: list[str] = []
    lines.append(f"\n{'=' * 70}")
    lines.append(f"  {name} — Evaluation Results (k={k})")
    lines.append(f"{'=' * 70}")
    lines.append(f"  Precision@{k}:  {result.precision:.3f}")
    lines.append(f"  Recall@{k}:     {result.recall:.3f}")
    lines.append(f"  NDCG@{k}:       {result.ndcg:.3f}")

    # Breakdown by query type
    types: dict[str, dict[str, list[float]]] = {}
    for entry, pq in zip(golden, result.per_query):
        qtype = entry.type
        if qtype not in types:
            types[qtype] = {"p": [], "r": [], "n": []}
        types[qtype]["p"].append(pq.precision)
        types[qtype]["r"].append(pq.recall)
        types[qtype]["n"].append(pq.ndcg)

    if len(types) > 1:
        lines.append("\n  By Query Type:")
        lines.append(f"  {'Type':<12} {'Count':>5} {'P@' + str(k):>8} {'R@' + str(k):>8} {'NDCG@' + str(k):>8}")
        lines.append(f"  {'-' * 12} {'-' * 5} {'-' * 8} {'-' * 8} {'-' * 8}")
        for qtype, scores in sorted(types.items()):
            n = len(scores["p"])
            p = sum(scores["p"]) / n
            r = sum(scores["r"]) / n
            ndcg = sum(scores["n"]) / n
            lines.append(f"  {qtype:<12} {n:5d} {p:8.3f} {r:8.3f} {ndcg:8.3f}")

    lines.append("\n  Per-Query Breakdown:")
    lines.append(f"  {'Type':<10} {'Query':<47} {'P':>5} {'R':>5} {'NDCG':>6}  Retrieved")
    lines.append(f"  {'-' * 10} {'-' * 47} {'-' * 5} {'-' * 5} {'-' * 6}  {'-' * 30}")
    for entry, pq in zip(golden, result.per_query):
        qtype = entry.type[:9]
        q_short = pq.query[:45] + ".." if len(pq.query) > 47 else pq.query
        files = ", ".join(f[:20] for f in pq.retrieved_files[:3])
        lines.append(f"  {qtype:<10} {q_short:<47} {pq.precision:5.2f} {pq.recall:5.2f} {pq.ndcg:6.2f}  {files}")

    return "\n".join(lines)


def format_comparison(results: dict[str, EvalResult], k: int) -> str:
    """Format side-by-side comparison of all backends.

    Returns:
        Formatted multi-line comparison string.
    """
    names = list(results.keys())
    lines: list[str] = []
    lines.append(f"\n{'=' * 70}")
    lines.append(f"  Cross-Backend Comparison (k={k})")
    lines.append(f"{'=' * 70}")

    header = f"  {'Metric':<15}"
    for name in names:
        header += f" {name:>12}"
    lines.append(header)
    lines.append(f"  {'-' * 15}" + f" {'-' * 12}" * len(names))

    for metric in ["precision", "recall", "ndcg"]:
        row = f"  {metric + '@' + str(k):<15}"
        for name in names:
            row += f" {getattr(results[name], metric):12.3f}"
        lines.append(row)

    if len(names) > 1:
        lines.append("\n  Pairwise Deltas:")
        lines.append(f"  {'Comparison':<28} {'P@' + str(k):>8} {'R@' + str(k):>8} {'NDCG@' + str(k):>8}")
        lines.append(f"  {'-' * 28} {'-' * 8} {'-' * 8} {'-' * 8}")
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                label = f"{names[j]} vs {names[i]}"
                dp = results[names[j]].precision - results[names[i]].precision
                dr = results[names[j]].recall - results[names[i]].recall
                dn = results[names[j]].ndcg - results[names[i]].ndcg
                lines.append(f"  {label:<28} {_fmt_delta(dp):>8} {_fmt_delta(dr):>8} {_fmt_delta(dn):>8}")

    return "\n".join(lines)


def run_evaluation(config: EvalConfig, dataset_path: str) -> dict[str, EvalResult]:
    """Run evaluation across all configured backends.

    Args:
        config: Validated evaluation config.
        dataset_path: Path to golden dataset JSONL file.

    Returns:
        Dict mapping backend name -> EvalResult.
    """
    golden = load_golden_dataset(dataset_path)
    logger.info("RAG Evaluation — %d queries, k=%d", len(golden), config.k)

    all_results: dict[str, EvalResult] = {}

    # Bedrock KB backends
    for bk in config.backends.bedrock_kb:
        logger.info("Running %s evaluation...", bk.name)
        source_map = bk.build_source_map(config.documents)
        bedrock_evaluator = BedrockKBEvaluator(
            knowledge_base_id=bk.knowledge_base_id,
            source_map=source_map,
            region=config.region,
            k=config.k,
        )
        all_results[bk.name] = bedrock_evaluator.evaluate(golden)

    # LISA API backends (OpenSearch, PGVector, etc.)
    # Group by (api_url, deployment_name) to reuse clients
    client_cache: dict[tuple[str, str], LisaApi] = {}
    for lisa_backend in config.backends.lisa_api:
        cache_key = (lisa_backend.api_url, lisa_backend.deployment_name)
        if cache_key not in client_cache:
            logger.info("Authenticating to %s...", lisa_backend.deployment_name)
            client_cache[cache_key] = _create_lisa_client(lisa_backend, config.region)

        logger.info("Running %s evaluation...", lisa_backend.name)
        client = client_cache[cache_key]
        source_map = lisa_backend.build_source_map(config.documents)
        lisa_evaluator = LisaApiEvaluator(
            client=client,
            repo_id=lisa_backend.repo_id,
            collection_id=lisa_backend.collection_id,
            source_map=source_map,
            k=config.k,
        )
        all_results[lisa_backend.name] = lisa_evaluator.evaluate(golden)

    return all_results
