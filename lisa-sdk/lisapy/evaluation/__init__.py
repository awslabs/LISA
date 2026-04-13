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

"""RAG evaluation module for measuring retrieval quality.

Provides metric functions, golden dataset loading, and evaluator classes
for Bedrock Knowledge Bases and LISA API backends (OpenSearch, PGVector).
"""

from .bedrock_kb import BedrockKBEvaluator
from .config import BedrockKBBackend, EvalConfig, LisaApiBackend, load_eval_config
from .dataset import load_golden_dataset
from .lisa_api import LisaApiEvaluator
from .metrics import deduplicate_sources, ndcg_at_k, precision_at_k, recall_at_k
from .runner import run_evaluation
from .types import EvalResult, GoldenDatasetEntry, QueryResult

__all__ = [
    "GoldenDatasetEntry",
    "QueryResult",
    "EvalResult",
    "deduplicate_sources",
    "precision_at_k",
    "recall_at_k",
    "ndcg_at_k",
    "load_golden_dataset",
    "BedrockKBEvaluator",
    "LisaApiEvaluator",
    "EvalConfig",
    "BedrockKBBackend",
    "LisaApiBackend",
    "load_eval_config",
    "run_evaluation",
]
