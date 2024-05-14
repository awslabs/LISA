"""
REST API resources.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""
from enum import Enum
from typing import Any, Dict, Union

from pydantic import BaseModel, Field


class RestApiResource(str, Enum):
    """REST API resource."""

    # Model info
    LIST_MODELS = "listModels"
    DESCRIBE_MODEL = "describeModel"
    DESCRIBE_MODELS = "describeModels"

    # Run models
    EMBEDDINGS = "embeddings"
    GENERATE = "generate"
    GENERATE_STREAM = "generateStream"


class ModelType(str, Enum):
    """Valid model types."""

    EMBEDDING = "embedding"
    TEXTGEN = "textgen"


class _BaseModelRequest(BaseModel):
    """Base model resource."""

    provider: str = Field(..., description="The backend provider for the model.")
    modelName: str = Field(..., description="The model name.")
    text: Union[str, list[str]] = Field(..., description="The input text(s) to be processed by the model.")
    modelKwargs: Dict[str, Any] = Field(default={}, description="Arguments to the model.")


class EmbeddingsRequest(_BaseModelRequest):
    """Create text embeddings."""


class GenerateRequest(_BaseModelRequest):
    """Run text generation."""


class GenerateStreamRequest(_BaseModelRequest):
    """Run text generation with streaming."""
