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

"""Evaluator for Amazon Bedrock Knowledge Bases."""

import boto3

from .metrics import ndcg_at_k, precision_at_k, recall_at_k
from .types import EvalResult, GoldenDatasetEntry, QueryResult


class BedrockKBEvaluator:
    """Evaluate retrieval quality of a Bedrock Knowledge Base.

    Calls the Bedrock Agent Runtime retrieve() API and computes
    Precision@k, Recall@k, and NDCG@k against a golden dataset.

    Args:
        knowledge_base_id: The Bedrock Knowledge Base ID.
        source_map: Mapping of short document names to full S3 URIs.
        region: AWS region for the Bedrock client.
        k: Number of top results to evaluate.
    """

    def __init__(
        self,
        knowledge_base_id: str,
        source_map: dict[str, str],
        region: str = "us-east-1",
        k: int = 5,
    ) -> None:
        self.knowledge_base_id = knowledge_base_id
        self.source_map = source_map
        self.region = region
        self.k = k
        self._client = boto3.client("bedrock-agent-runtime", region_name=region)

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
            resp = self._client.retrieve(
                knowledgeBaseId=self.knowledge_base_id,
                retrievalQuery={"text": entry.query},
                retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": self.k}},
            )
            retrieved = [r["location"]["s3Location"]["uri"] for r in resp["retrievalResults"]]
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
