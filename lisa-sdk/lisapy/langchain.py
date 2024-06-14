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

"""Langchain adapter."""
from typing import Any, cast, Iterator, List, Mapping, Optional, Union

from httpx import AsyncClient as HttpAsyncClient
from httpx import Client as HttpClient
from langchain.callbacks.manager import CallbackManagerForLLMRun
from langchain.llms.base import LLM
from langchain.schema.output import GenerationChunk
from langchain_core.embeddings import Embeddings
from langchain_core.pydantic_v1 import BaseModel, Extra
from langchain_openai import OpenAIEmbeddings
from pydantic import PrivateAttr

from .main import FoundationModel, Lisa


class LisaTextgen(LLM):
    """Lisa text generation adapter.

    To use, you should have the `lisapy` python package installed and
    a Lisa API available.
    """

    provider: str
    """Provider of the LISA serve model  e.g., ecs.textgen.tgi."""

    model_name: str
    """Name of LISA serve model e.g. Mixtral-8x7B-Instruct-v0.1"""

    client: Lisa
    """An instance of the Lisa client."""

    foundation_model: FoundationModel = PrivateAttr(default_factory=None)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.foundation_model = self.client.describe_model(self.provider, self.model_name)

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "lisa_inference"

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        return {
            "provider": self.provider,
            "model_name": self.model_name,
            "client": self.client,
            "foundation_model": self.foundation_model,
        }

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> str:
        if self.foundation_model.streaming:
            completion = ""
            for chunk in self._stream(prompt, stop, run_manager, **kwargs):
                completion += chunk.text
            return completion

        text, _ = self.client.generate(prompt, self.foundation_model)

        return text  # type: ignore

    def _stream(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[GenerationChunk]:
        for resp in self.client.generate_stream(prompt, self.foundation_model):
            # yield text, if any
            if resp.token:
                chunk = GenerationChunk(text=resp.token)
                yield chunk
                if run_manager:
                    run_manager.on_llm_new_token(chunk.text)


class LisaOpenAIEmbeddings(BaseModel, Embeddings):
    """LISA text embedding adapter."""

    lisa_openai_api_base: str
    """LISA REST API URI."""

    model: str
    """Model name for Embeddings API."""

    api_token: str
    """API Token for communicating with LISA Serve. This can be a custom API token or the IdP Bearer token."""

    verify: Union[bool, str]
    """Cert path or option for verifying SSL"""

    embedding_model: OpenAIEmbeddings = PrivateAttr(default_factory=None)
    """OpenAI-compliant client for making requests against embedding model."""

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid
        arbitrary_types_allowed = True

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.embedding_model = OpenAIEmbeddings(
            openai_api_base=self.lisa_openai_api_base,
            openai_api_key=self.api_token,
            model=self.model,
            model_kwargs={
                "encoding_format": "float",  # keep values as floats because base64 is not widely supported
            },
            http_async_client=HttpAsyncClient(verify=self.verify),
            http_client=HttpClient(verify=self.verify),
        )

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Use OpenAI API to embed a list of documents."""
        return cast(List[List[float]], self.embedding_model.embed_documents(texts=texts))

    def embed_query(self, text: str) -> List[float]:
        """Use OpenAI API to embed a text."""
        return cast(List[float], self.embedding_model.embed_query(text=text))

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Use OpenAI API to embed a list of documents."""
        return cast(List[List[float]], await self.embedding_model.aembed_documents(texts=texts))

    async def aembed_query(self, text: str) -> List[float]:
        """Use OpenAI API to embed a text."""
        return cast(List[float], await self.embedding_model.aembed_query(text=text))


class LisaEmbeddings(BaseModel, Embeddings):
    """Lisa text embedding adapter.

    To use, you should have the `lisapy` python package installed and
    a Lisa API available.
    """

    provider: str
    """Provider of the LISA serve model  e.g., ecs.textgen.tgi."""

    model_name: str
    """Name of LISA serve model e.g. Mixtral-8x7B-Instruct-v0.1"""

    client: Lisa
    """An instance of the Lisa client."""

    foundation_model: FoundationModel = PrivateAttr(default_factory=None)

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid
        arbitrary_types_allowed = True

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.foundation_model = self.client.describe_model(self.provider, self.model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Compute doc embeddings using a LISA model.

        Parameters
        ----------
        texts : List[str]
            The list of texts to embed.

        Returns
        -------
        List[List[float]]
            List of embeddings, one for each text.
        """
        return self.client.embed(texts, self.foundation_model)

    def embed_query(self, text: str) -> List[float]:
        """Compute query embeddings using a LISA model.

        Parameters
        ----------
        text : str
            The text to embed.

        Returns
        -------
        List[float]
            Embedding for the text.
        """
        return self.client.embed(text, self.foundation_model)[0]

    async def aembed_query(self, text: str) -> List[float]:
        """Asynchronous compute query embeddings using a LISA model.

        Parameters
        ----------
        text : str
            The text to embed.

        Returns
        -------
        List[float]
            Embedding for the text.
        """
        return (await self.client.aembed(text, self.foundation_model))[0]

    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        """Asynchronous compute doc embeddings using a LISA model.

        Parameters
        ----------
        texts : List[str]
            The list of texts to embed.

        Returns
        -------
        List[List[float]]
            List of embeddings, one for each text.
        """
        return await self.client.aembed(texts, self.foundation_model)
