"""
SDK types.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ModelType(str, Enum):
    """Type of foundation models."""

    TEXTGEN = "textgen"
    EMBEDDING = "embedding"


class ModelKwargs(BaseModel):
    """Model arguments."""

    model_config = ConfigDict(extra="allow")


class FoundationModel(BaseModel):
    """A foundation model registered in LISA."""

    model_config = ConfigDict(use_enum_values=True, protected_namespaces=())

    provider: str = Field(..., description="The foundation model provider, e.g. ecs.textgen.tgi.")
    model_type: ModelType = Field(..., description="The type of foundation model.")
    model_name: str = Field(..., description="The model name.")
    model_kwargs: Optional[ModelKwargs] = Field(default_factory=None, description="The model arguments.")
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
    finish_reason: Optional[str] = Field(None, description="Generation finish reason when stream is complete.")
    generated_tokens: Optional[int] = Field(None, description="Number of generated tokens when stream is complete.")
