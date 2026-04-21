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

from .base import BaseEvaluator


class BedrockKBEvaluator(BaseEvaluator):
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
        super().__init__(source_map=source_map, k=k)
        self.knowledge_base_id = knowledge_base_id
        self.region = region
        self._client = boto3.client("bedrock-agent-runtime", region_name=region)

    def _retrieve(self, query: str) -> list[str]:
        """Call Bedrock Agent Runtime retrieve() and return source URIs."""
        resp = self._client.retrieve(
            knowledgeBaseId=self.knowledge_base_id,
            retrievalQuery={"text": query},
            retrievalConfiguration={"vectorSearchConfiguration": {"numberOfResults": self.k}},
        )
        return [r["location"]["s3Location"]["uri"] for r in resp["retrievalResults"]]
