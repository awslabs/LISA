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

"""Model adapter and kwargs validator for ECS embedding instructor model endpoints."""
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
