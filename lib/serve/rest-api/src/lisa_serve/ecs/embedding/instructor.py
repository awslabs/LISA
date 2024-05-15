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
from typing import Any, Dict

from aiohttp import ClientSession
from loguru import logger
from pydantic import BaseModel

from ...base import EmbeddingModelAdapter, EmbedQueryResponse, escape_curly_brackets
from ...registry import registry


class EcsEmbeddingInstructorValidator(BaseModel):
    """Model kwargs validator for ECS embedding instructor model endpoints.

    Parameters
    ----------
    instruction : str, default="Represent the document:"
        Instructor for customized embeddings.
    """

    instruction: str = "Represent the document:"


class EcsEmbeddingInstructorAdapter(EmbeddingModelAdapter):
    """Model adapter for ECS embedding instructor model endpoints.

    Parameters
    ----------
    model_name : str
        Model name.

    endpoint_url : str
        Endpoint URL.
    """

    def __init__(self, *, model_name: str, endpoint_url: str) -> None:
        super().__init__(model_name=model_name, endpoint_url=endpoint_url)

        # PyTorch DLC has the endpoint at path /predictions/model
        self.endpoint_url = f"{self.endpoint_url.rstrip('/')}/predictions/model"  # type: ignore

    async def embed_query(self, *, text: str, model_kwargs: Dict[str, Any]) -> EmbedQueryResponse:  # type: ignore
        """Embed data.

        Parameters
        ----------
        text : str
            Input text to embed.

        model_kwargs : Dict[str, Any]
            Arguments and configurations specific to the model.

        Returns
        -------
        EmbedQueryResponse
            Embedding model response.
        """
        # Unpack instruction
        instruction = model_kwargs["instruction"]
        payload = {
            "instruction": instruction,
            "text": text,
        }

        async with ClientSession() as session:
            async with session.post(self.endpoint_url, json=payload) as server_response:
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
    provider="ecs.embedding.instructor",
    adapter=EcsEmbeddingInstructorAdapter,
    validator=EcsEmbeddingInstructorValidator,
)
