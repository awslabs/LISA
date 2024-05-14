"""
Base model adapters and responses.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""
import re
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional

from pydantic import BaseModel, Field

#############
# RESPONSES #
#############


class EmbedQueryResponse(BaseModel):
    """Response for embed_query method."""

    embeddings: List[List[float]] = Field(..., description="Batch of text embeddings.")


class GenerateResponse(BaseModel):
    """Response for generate method."""

    generatedText: str = Field(..., description="Generated text.")
    generatedTokens: Optional[int] = Field(..., description="Number of generated tokens.")
    finishReason: Optional[str] = Field(None, description="Reason for finishing text generation.")


class Token(BaseModel):
    """Token for generate_stream method."""

    text: str = Field(..., description="Token text.")
    special: Optional[bool] = Field(None, description="Whether token is a special token.")


class GenerateStreamResponse(BaseModel):
    """Response for generate_stream method."""

    token: Token
    generatedTokens: Optional[int] = Field(..., description="Number of generated tokens.")
    finishReason: Optional[str] = Field(None, description="Reason for finishing text generation.")


############
# ADAPTERS #
############


class EmbeddingModelAdapter(ABC):
    """Abstract base class for embedding model adapters.

    Parameters
    ----------
    model_name : str
        Model name.

    endpoint_url : str, default=None
        Endpoint URL.
    """

    def __init__(self, *, model_name: str, endpoint_url: Optional[str] = None) -> None:
        self.model_name = model_name
        self.endpoint_url = endpoint_url

    @abstractmethod
    def embed_query(self, *, text: str, model_kwargs: Dict[str, Any]) -> EmbedQueryResponse:
        """Embed query.

        Parameters
        ----------
        text : str
            Input text to embed.

        model_kwargs : Dict[str, Any]
            Arguments to embedding model.

        Returns
        -------
        EmbedQueryResponse
            Embedding model response.
        """
        pass


class TextGenModelAdapter(ABC):
    """Abstract base class for text generation model adapters.

    Parameters
    ----------
    model_name : str
        Model name.

    endpoint_url : str, default=None
        Endpoint URL.
    """

    def __init__(self, *, model_name: str, endpoint_url: Optional[str] = None) -> None:
        self.model_name = model_name
        self.endpoint_url = endpoint_url

    @abstractmethod
    def generate(self, *, text: str, model_kwargs: Dict[str, Any]) -> GenerateResponse:
        """Text generation.

        Parameters
        ----------
        text : str
            Prompt input text.

        model_kwargs : Dict[str, Any]
            Arguments to text generation model.

        Returns
        -------
        GenerateResponse
            Text generation model response.
        """
        pass


class StreamTextGenModelAdapter(ABC):
    """Abstract base class for text generation model adapters with streaming option."""

    @abstractmethod
    def generate_stream(
        self,
        *,
        text: str,
        model_kwargs: Dict[str, Any],
    ) -> AsyncGenerator[GenerateStreamResponse, None]:
        """Text generation with token streaming.

        Parameters
        ----------
        text : str
            Prompt input text.

        model_kwargs : Dict[str, Any]
            Arguments to text generation model.

        Returns
        -------
        AsyncGenerator[GenerateStreamResponse, None]
            Text generation model response with streaming.
        """
        pass


def escape_curly_brackets(s: str) -> str:
    """Escapes curly brackets in the given string for downstream use with `str.format()`.

    Parameters
    ----------
    s : str
        String to be escaped.

    Returns
    -------
    str
        Escaped string.
    """
    return re.sub(r"({|})", r"\1\1", s)
