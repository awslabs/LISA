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

"""Evaluation config schema and loader.

Config is a YAML file that defines:
- Region and evaluation parameters (k)
- Document registry (short name → filename)
- Backend definitions (Bedrock KB and/or LISA API)

Each backend has an s3_bucket prefix. The source_map is built at runtime
by combining the document registry with the backend's bucket.
"""

from typing import Any

import yaml
from pydantic import BaseModel, Field


class BedrockKBBackend(BaseModel):
    """Configuration for a Bedrock Knowledge Base backend."""

    name: str = Field(..., description="Display name for this backend.")
    knowledge_base_id: str = Field(..., description="Bedrock Knowledge Base ID.")
    s3_bucket: str = Field(..., description="S3 bucket prefix for source matching.")

    def build_source_map(self, documents: dict[str, str]) -> dict[str, str]:
        """Build source_map from document registry + this backend's bucket."""
        return {k: f"{self.s3_bucket}/{v}" for k, v in documents.items()}


class LisaApiBackend(BaseModel):
    """Configuration for a LISA API backend (OpenSearch, PGVector, etc.)."""

    name: str = Field(..., description="Display name for this backend.")
    api_url: str = Field(..., description="LISA API Gateway URL.")
    deployment_name: str = Field(..., description="LISA deployment name for auth.")
    repo_id: str = Field(..., description="Repository ID.")
    collection_id: str = Field("default", description="Collection ID within the repository.")
    s3_bucket: str = Field(..., description="S3 bucket prefix for source matching.")

    def build_source_map(self, documents: dict[str, str]) -> dict[str, str]:
        """Build source_map from document registry + this backend's bucket."""
        return {k: f"{self.s3_bucket}/{v}" for k, v in documents.items()}


class Backends(BaseModel):
    """Container for all backend configurations."""

    bedrock_kb: list[BedrockKBBackend] = Field(default_factory=list, description="Bedrock KB backends.")
    lisa_api: list[LisaApiBackend] = Field(default_factory=list, description="LISA API backends.")


class EvalConfig(BaseModel):
    """Top-level evaluation configuration."""

    region: str = Field(..., description="AWS region.")
    k: int = Field(5, description="Number of top results to evaluate.")
    documents: dict[str, str] = Field(..., description="Short name → filename mapping.")
    backends: Backends = Field(default_factory=Backends, description="Backend configurations.")


def load_eval_config(path: str) -> EvalConfig:
    """Load and validate an evaluation config from a YAML file.

    Args:
        path: Filesystem path to a YAML config file.

    Returns:
        Validated EvalConfig model.

    Raises:
        FileNotFoundError: If path does not exist.
        pydantic.ValidationError: If config fails validation.
    """
    raw: dict[str, Any] = {}
    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    return EvalConfig.model_validate(raw)  # type: ignore[no-any-return]
