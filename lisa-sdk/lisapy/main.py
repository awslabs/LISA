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

"""LISA SDK."""
import json
import logging
import sys
from collections.abc import AsyncGenerator, Generator
from typing import Any

import requests
from aiohttp import ClientSession, ClientTimeout
from pydantic import BaseModel, ConfigDict, Field, field_validator
from requests import Session

from .errors import parse_error
from .types import FoundationModel, Response, StreamingResponse

logging.basicConfig(level=logging.INFO)

API_VERSION = "v2"


def on_llm_new_token(token: str) -> None:
    """Handle new tokens during streaming."""
    sys.stdout.write(token)
    sys.stdout.flush()


class LisaLlm(BaseModel):
    """A wrapper around the LISA LLM REST API."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    url: str = Field(..., description="REST API url for LiteLLM")
    headers: dict[str, str] | None = Field(None, description="Headers for request.")
    cookies: dict[str, str] | None = Field(None, description="Cookies for request.")
    timeout: int = Field(10, description="Timeout in minutes request.")
    verify: str | bool | None = Field(None, description="Whether to verify SSL certificates.")
    async_timeout: ClientTimeout | None = None  # Do not provide a default value here
    _session: Session

    @field_validator("url")
    def validate_url(cls: "LisaLlm", v: str) -> str:
        """Validate URL is properly formatted."""
        url = v.rstrip("/")
        if not url.endswith(API_VERSION):
            url = f"{url}/{API_VERSION}"
        return url

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self._session = requests.Session()
        if self.headers:
            self._session.headers.update(self.headers)
        if self.verify is not None:
            self._session.verify = self.verify
        if self.cookies:
            self._session.cookies.update(self.cookies)

        self.async_timeout = ClientTimeout(self.timeout * 60)

    def list_models(self) -> list[dict[str, Any]]:
        """List all foundation models.

        Returns
        -------
        List[FoundationModel]
            List of available text generation and embedding foundation models.
        """
        response = self._session.get(f"{self.url}/serve/models")
        if response.status_code == 200:
            json_models = response.json()
            models: list[dict] = json_models.get("data")
        else:
            raise parse_error(response.status_code, response)
        return models

    def _build_chat_payload(self, prompt: str, model: FoundationModel, stream: bool = False) -> dict:
        """Build an OpenAI-compatible chat completion payload."""
        payload: dict[str, Any] = {
            "model": model.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream,
        }
        if model.model_kwargs:
            kwargs = model.model_kwargs.model_dump(exclude_none=True)
            if "max_new_tokens" in kwargs:
                payload["max_tokens"] = kwargs.pop("max_new_tokens")
            payload.update(kwargs)
        return payload

    def generate(self, prompt: str, model: FoundationModel) -> Response:
        """Generate text using OpenAI-compatible chat completions endpoint.

        Parameters
        ----------
        prompt : str
            Input prompt.

        model : FoundationModel
            Foundation model for text generation.

        Returns
        -------
        Response
            Text generation response.
        """
        payload = self._build_chat_payload(prompt, model, stream=False)
        response = self._session.post(f"{self.url}/serve/chat/completions", json=payload)
        if response.status_code == 200:
            output = response.json()
            choice = output["choices"][0]
            usage = output.get("usage", {})
            return Response(
                generated_text=choice["message"]["content"],
                generated_tokens=usage.get("completion_tokens", 0),
                finish_reason=choice.get("finish_reason", "stop"),
            )
        else:
            raise parse_error(response.status_code, response)

    async def agenerate(self, prompt: str, model: FoundationModel) -> Response:
        """Generate text asynchronously using OpenAI-compatible chat completions.

        Parameters
        ----------
        prompt : str
            Input prompt.

        model : FoundationModel
            Foundation model for text generation.

        Returns
        -------
        Response
            Text generation response.
        """
        payload = self._build_chat_payload(prompt, model, stream=False)
        async with ClientSession(
            headers=self.headers,
            cookies=self.cookies,
            timeout=self.async_timeout,
        ) as session:
            async with session.post(f"{self.url}/serve/chat/completions", json=payload, ssl=self.verify) as response:
                output = await response.json()
                if response.status == 200:
                    choice = output["choices"][0]
                    usage = output.get("usage", {})
                    return Response(
                        generated_text=choice["message"]["content"],
                        generated_tokens=usage.get("completion_tokens", 0),
                        finish_reason=choice.get("finish_reason", "stop"),
                    )
                else:
                    raise parse_error(response.status, response)

    def generate_stream(self, prompt: str, model: FoundationModel) -> Generator[StreamingResponse]:
        """Generate text with streaming using OpenAI-compatible SSE format.

        Parameters
        ----------
        prompt : str
            Input prompt.

        model : FoundationModel
            Foundation model for text generation.

        Returns
        -------
        Generator[StreamingResponse, None, None]
            Text generation streaming response.
        """
        payload = self._build_chat_payload(prompt, model, stream=True)
        response = self._session.post(f"{self.url}/serve/chat/completions", json=payload, stream=True)
        if response.status_code == 200:
            for line in response.iter_lines():
                if not line:
                    continue
                text = line.decode("utf-8") if isinstance(line, bytes) else line
                if not text.startswith("data:"):
                    continue
                data_str = text[len("data:") :].strip()
                if data_str == "[DONE]":
                    break
                chunk = json.loads(data_str)
                delta = chunk.get("choices", [{}])[0].get("delta", {})
                finish = chunk.get("choices", [{}])[0].get("finish_reason")
                usage = chunk.get("usage")
                token_text = delta.get("content", "")
                if finish:
                    yield StreamingResponse(
                        token=token_text,
                        finish_reason=finish,
                        generated_tokens=usage.get("completion_tokens") if usage else None,
                    )
                elif token_text:
                    yield StreamingResponse(token=token_text)
        else:
            raise parse_error(response.status_code, response)

    async def agenerate_stream(self, prompt: str, model: FoundationModel) -> AsyncGenerator[StreamingResponse]:
        """Generate text with async streaming using OpenAI-compatible SSE format.

        Parameters
        ----------
        prompt : str
            Input prompt.

        model : FoundationModel
            Foundation model for text generation.

        Returns
        -------
        AsyncGenerator[StreamingResponse, None]
            Text generation streaming response.
        """
        payload = self._build_chat_payload(prompt, model, stream=True)
        async with ClientSession(
            headers=self.headers,
            cookies=self.cookies,
            timeout=self.async_timeout,
        ) as session:
            async with session.post(f"{self.url}/serve/chat/completions", json=payload, ssl=self.verify) as response:
                if response.status != 200:
                    raise parse_error(response.status, response)
                async for line in response.content:
                    text = line.decode("utf-8").strip() if isinstance(line, bytes) else line.strip()
                    if not text or not text.startswith("data:"):
                        continue
                    data_str = text[len("data:") :].strip()
                    if data_str == "[DONE]":
                        break
                    chunk = json.loads(data_str)
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    finish = chunk.get("choices", [{}])[0].get("finish_reason")
                    usage = chunk.get("usage")
                    token_text = delta.get("content", "")
                    if finish:
                        yield StreamingResponse(
                            token=token_text,
                            finish_reason=finish,
                            generated_tokens=usage.get("completion_tokens") if usage else None,
                        )
                    elif token_text:
                        yield StreamingResponse(token=token_text)

    def embed(self, texts: str | list[str], model: FoundationModel) -> list[list[float]]:
        """Generate text embeddings using OpenAI-compatible embeddings endpoint.

        Parameters
        ----------
        texts : Union[str, List[str]]
            Input texts.

        model : FoundationModel
            Foundation model for text embeddings.

        Returns
        -------
        List[List[float]]
            Text embeddings as a batched response.
        """
        payload: dict[str, Any] = {
            "model": model.model_name,
            "input": texts if isinstance(texts, list) else [texts],
        }
        response = self._session.post(f"{self.url}/serve/embeddings", json=payload)
        if response.status_code == 200:
            output = response.json()
            return [item["embedding"] for item in output["data"]]
        else:
            raise parse_error(response.status_code, response)

    async def aembed(self, texts: str | list[str], model: FoundationModel) -> list[list[float]]:
        """Generate text embeddings asynchronously using OpenAI-compatible endpoint.

        Parameters
        ----------
        texts : Union[str, List[str]]
            Input texts.

        model : FoundationModel
            Foundation model for text embeddings.

        Returns
        -------
        List[List[float]]
            Text embeddings as a batched response.
        """
        payload: dict[str, Any] = {
            "model": model.model_name,
            "input": texts if isinstance(texts, list) else [texts],
        }
        async with ClientSession(
            headers=self.headers,
            cookies=self.cookies,
            timeout=self.async_timeout,
        ) as session:
            async with session.post(f"{self.url}/serve/embeddings", json=payload, ssl=self.verify) as response:
                if response.status != 200:
                    raise parse_error(response.status, response)
                output = await response.json()
                return [item["embedding"] for item in output["data"]]

    def __del__(self) -> None:
        """Close session."""
        try:
            self._session.close()
        except Exception as e:
            logging.debug(f"Error closing session during cleanup: {e}")


"""
TODO: Create support for the following
# List models
"models",
"v1/models",
# Model Info
"model/info" "v1/model/info"
# Text completions
"chat/completions",
"v1/chat/completions",
"completions",
"v1/completions",
# Embeddings
"embeddings",
"v1/embeddings",
# Create images
"images/generations",
"v1/images/generations",
# Audio routes
"audio/speech",
"v1/audio/speech",
"audio/transcriptions",
"v1/audio/transcriptions",
# Health check routes
"health",
"health/readiness",
"health/liveliness",
"""
