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

"""LISA SDK types."""
from __future__ import annotations

from enum import Enum
from typing import Any, TypedDict

from pydantic import BaseModel, ConfigDict, Field


class ModelType(str, Enum):
    """Type of foundation models."""

    TEXTGEN = "textgen"
    EMBEDDING = "embedding"
    VIDEOGEN = "videogen"


class ModelKwargs(BaseModel):
    """Model arguments."""

    model_config = ConfigDict(extra="allow")


class FoundationModel(BaseModel):
    """A foundation model registered in LISA."""

    model_config = ConfigDict(use_enum_values=True, protected_namespaces=())

    provider: str = Field(..., description="The foundation model provider, e.g. ecs.textgen.tgi.")
    model_type: ModelType = Field(..., description="The type of foundation model.")
    model_name: str = Field(..., description="The model name.")
    model_kwargs: ModelKwargs | None = Field(
        default_factory=None,
        description="The model arguments.",
    )
    streaming: bool = Field(False, description="Whether the model supports streaming.")

    def to_string(self) -> str:
        """Create full model name."""
        return f"{self.provider}.{self.model_name}"

    @classmethod
    def from_dict(cls, d: dict) -> FoundationModel:
        """Create a FoundationModel object from a dictionary."""
        return cls(
            provider=d["provider"],
            model_name=d["modelName"],
            model_type=d["modelType"],
            model_kwargs=d["modelKwargs"],
            streaming=d.get("streaming", False),
        )


class Response(BaseModel):
    """Response from text generation endpoint."""

    generated_text: str = Field(..., description="Generated text.")
    finish_reason: str = Field(..., description="Generation finish reason.")
    generated_tokens: int = Field(..., description="Number of generated tokens.")


class StreamingResponse(BaseModel):
    """Response from text generation with streaming endpoint."""

    token: str = Field(..., description="Generated token")
    finish_reason: str | None = Field(None, description="Generation finish reason when stream is complete.")
    generated_tokens: int | None = Field(None, description="Number of generated tokens when stream is complete.")


class ModelRequest(TypedDict, total=False):
    """Type definition for model creation requests."""

    modelId: str
    modelName: str
    modelDescription: str
    modelUrl: str
    streaming: bool
    multiModal: bool
    modelType: str
    instanceType: str
    inferenceContainer: str
    baseImage: str
    features: list[dict[str, str]]
    allowedGroups: list[str]
    containerConfig: dict[str, Any]
    autoScalingConfig: dict[str, Any]
    loadBalancerConfig: dict[str, Any]


class BedrockModelRequest(TypedDict, total=False):
    """Type definition for Bedrock model creation requests."""

    modelId: str
    modelName: str
    modelDescription: str
    modelUrl: str
    streaming: bool
    multiModal: bool
    modelType: str
    features: list[dict[str, str]]
    allowedGroups: list[str]
    apiKey: str


class RagRepositoryConfig(TypedDict, total=False):
    """Type definition for RAG repository configuration."""

    repositoryId: str
    repositoryName: str
    embeddingModelId: str
    type: str
    opensearchConfig: dict[str, Any]
    rdsConfig: dict[str, Any]
    bedrockKnowledgeBaseConfig: dict[str, Any]
    pipelines: list[dict[str, Any]]
    allowedGroups: list[str]
