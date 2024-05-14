"""
Model adapter and kwargs validator for ECS embedding instructor model endpoints.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""
from typing import Any, Dict, Union

from aiohttp import ClientSession
from loguru import logger
from pydantic import BaseModel

from ...base import EmbeddingModelAdapter, EmbedQueryResponse, escape_curly_brackets
from ...registry import registry


class EcsEmbeddingTeiValidator(BaseModel):
    """Model kwargs validator for ECS TEI model endpoints.

    Parameters
    ----------
    normalize : bool, default=True
        Normalizes embeddings when enabled.
    truncate : bool, default=True
        Truncates inputs to model context length when enabled.
    """

    normalize: bool = True
    truncate: bool = True


class EcsEmbeddingTeiAdapter(EmbeddingModelAdapter):
    """Model adapter for ECS TEI model endpoints.

    Parameters
    ----------
    model_name : str
        Model name.

    endpoint_url : str
        Endpoint URL.
    """

    def __init__(self, *, model_name: str, endpoint_url: str) -> None:
        super().__init__(model_name=model_name, endpoint_url=endpoint_url)

        self.endpoint_url = endpoint_url.rstrip("/")

    async def embed_query(self, *, text: Union[str, list[str]], model_kwargs: Dict[str, Any]) -> EmbedQueryResponse:  # type: ignore # noqa: E501
        """Embed data.

        Parameters
        ----------
        text : Union[str, list[str]]
            Input text(s) to embed.

        model_kwargs : Dict[str, Any]
            Arguments and configurations specific to the model.

        Returns
        -------
        EmbedQueryResponse
            Embedding model response.
        """
        # Unpack instruction
        payload = {"inputs": text, **model_kwargs}

        async with ClientSession() as session:
            async with session.post(
                self.endpoint_url, json=payload, headers={"Content-Type": "application/json"}
            ) as server_response:
                server_response.raise_for_status()
                server_response_json = await server_response.json()

                response = EmbedQueryResponse(embeddings=server_response_json)

                logger.debug(
                    f"Received: {escape_curly_brackets(response.json())}",
                    extra={"event": f"{self.__class__.__name__}:embed_query"},
                )
                return response


# Register the model
registry.register(
    provider="ecs.embedding.tei",
    adapter=EcsEmbeddingTeiAdapter,
    validator=EcsEmbeddingTeiValidator,
)
