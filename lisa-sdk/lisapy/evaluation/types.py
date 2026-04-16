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

"""Pydantic models for RAG evaluation."""

from pydantic import BaseModel, ConfigDict, Field


class GoldenDatasetEntry(BaseModel):
    """A single entry in the golden evaluation dataset."""

    model_config = ConfigDict(extra="allow")

    query: str = Field(..., description="The search query to evaluate.")
    expected: list[str] = Field(..., description="Short document names expected in results.")
    relevance: dict[str, int] = Field(default_factory=dict, description="Graded relevance per expected document.")
    type: str = Field("unknown", description="Query type: semantic, lexical, ambiguous, negative, adversarial.")


class QueryResult(BaseModel):
    """Evaluation metrics for a single query."""

    model_config = ConfigDict(extra="allow")

    query: str = Field(..., description="The original query.")
    query_type: str = Field("unknown", description="Query type from the golden dataset entry.")
    precision: float = Field(..., description="Precision@k for this query.")
    recall: float = Field(..., description="Recall@k for this query.")
    ndcg: float = Field(..., description="NDCG@k for this query.")
    retrieved_files: list[str] = Field(default_factory=list, description="Filenames of retrieved documents.")
    expected_files: list[str] = Field(default_factory=list, description="Filenames of expected documents.")


class EvalResult(BaseModel):
    """Aggregate evaluation results across all queries."""

    model_config = ConfigDict(extra="allow")

    precision: float = Field(..., description="Mean Precision@k across all queries.")
    recall: float = Field(..., description="Mean Recall@k across all queries.")
    ndcg: float = Field(..., description="Mean NDCG@k across all queries.")
    per_query: list[QueryResult] = Field(default_factory=list, description="Per-query breakdown.")
