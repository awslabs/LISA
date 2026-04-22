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
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from aiohttp import ClientSession, ClientTimeout, FormData
from pydantic import BaseModel, ConfigDict, Field, field_validator
from requests import Session

from .errors import parse_error
from .types import CompletionResponse, FoundationModel, ImageResponse, ModelInfoEntry, Response, StreamingResponse

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
        """List all models from the LiteLLM proxy.

        Returns:
        -------
        list[dict[str, Any]]
            List of model dicts in OpenAI format (id, object, created, owned_by).
        """
        response = self._session.get(f"{self.url}/serve/models")
        if response.status_code == 200:
            json_models = response.json()
            models: list[dict] = json_models.get("data")
        else:
            raise parse_error(response.status_code, response)
        return models

    def health(self) -> dict[str, Any]:
        """Check health of the LiteLLM proxy.

        Returns:
        -------
        dict[str, Any]
            Health status response from the proxy.
        """
        response = self._session.get(f"{self.url}/serve/health")
        if response.status_code == 200:
            data: dict[str, Any] = response.json()
            return data
        else:
            raise parse_error(response.status_code, response)

    def health_readiness(self) -> dict[str, Any]:
        """Check readiness of the LiteLLM proxy.

        Returns:
        -------
        dict[str, Any]
            Readiness status response from the proxy.
        """
        response = self._session.get(f"{self.url}/serve/health/readiness")
        if response.status_code == 200:
            data: dict[str, Any] = response.json()
            return data
        else:
            raise parse_error(response.status_code, response)

    def health_liveliness(self) -> dict[str, Any]:
        """Check liveliness of the LiteLLM proxy.

        Note: LiteLLM returns a plain string for this endpoint. The SDK
        normalizes it to ``{"status": "I'm alive!"}`` for a consistent
        dict return type across all health methods.

        Returns:
        -------
        dict[str, Any]
            Liveliness status response from the proxy.
        """
        response = self._session.get(f"{self.url}/serve/health/liveliness")
        if response.status_code == 200:
            result: Any = response.json()
            if isinstance(result, str):
                return {"status": result}
            data: dict[str, Any] = result
            return data
        else:
            raise parse_error(response.status_code, response)

    def get_model_info(self) -> list[ModelInfoEntry]:
        """Get detailed model information from the LiteLLM proxy.

        Returns the full LiteLLM model database including litellm_params,
        provider details, and model configuration.

        Returns:
        -------
        list[ModelInfoEntry]
            List of model info entries with name, params, and metadata.
        """
        response = self._session.get(f"{self.url}/serve/model/info")
        if response.status_code == 200:
            output = response.json()
            return [ModelInfoEntry(**entry) for entry in output.get("data", [])]
        else:
            raise parse_error(response.status_code, response)

    # OpenAI chat completions fields that can be passed at the top level
    _OPENAI_CHAT_FIELDS = frozenset(
        {
            "temperature",
            "top_p",
            "n",
            "stop",
            "max_tokens",
            "presence_penalty",
            "frequency_penalty",
            "logit_bias",
            "user",
            "seed",
            "tools",
            "tool_choice",
            "response_format",
        }
    )

    def _build_chat_payload(self, prompt: str, model: FoundationModel, stream: bool = False) -> dict[str, Any]:
        """Build an OpenAI-compatible chat completion payload."""
        payload: dict[str, Any] = {
            "model": model.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream,
        }
        if model.model_kwargs:
            kwargs = model.model_kwargs.model_dump(exclude_none=True)
            # Map HuggingFace-style param to OpenAI name
            if "max_new_tokens" in kwargs:
                payload["max_tokens"] = kwargs.pop("max_new_tokens")
            if "stop_sequences" in kwargs:
                payload["stop"] = kwargs.pop("stop_sequences")
            # Only include known OpenAI fields; drop provider-specific params
            for k, v in kwargs.items():
                if k in self._OPENAI_CHAT_FIELDS:
                    payload[k] = v
        return payload

    # OpenAI legacy completions fields that can be passed at the top level
    _OPENAI_COMPLETIONS_FIELDS = frozenset(
        {
            "temperature",
            "top_p",
            "n",
            "stop",
            "max_tokens",
            "presence_penalty",
            "frequency_penalty",
            "logit_bias",
            "user",
            "seed",
            "suffix",
            "echo",
            "best_of",
            "logprobs",
        }
    )

    # OpenAI image generation fields
    _OPENAI_IMAGE_FIELDS = frozenset({"n", "size", "quality", "response_format", "style", "user"})

    # OpenAI text-to-speech fields
    _OPENAI_TTS_FIELDS = frozenset({"response_format", "speed"})

    # OpenAI transcription fields
    _OPENAI_TRANSCRIPTION_FIELDS = frozenset({"language", "prompt", "response_format", "temperature"})

    def complete(self, prompt: str, model: str, **kwargs: Any) -> CompletionResponse:
        """Generate text using the legacy OpenAI completions endpoint.

        Parameters
        ----------
        prompt : str
            Input prompt string.

        model : str
            Model name as registered in LiteLLM.

        **kwargs : Any
            Additional OpenAI completions parameters (temperature, max_tokens, etc.).
            Unknown parameters are filtered out.

        Returns:
        -------
        CompletionResponse
            Legacy completion response with id, choices, and usage.
        """
        payload: dict[str, Any] = {"model": model, "prompt": prompt}
        for k, v in kwargs.items():
            if k in self._OPENAI_COMPLETIONS_FIELDS:
                payload[k] = v
        response = self._session.post(f"{self.url}/serve/completions", json=payload)
        if response.status_code == 200:
            return CompletionResponse(**response.json())
        else:
            raise parse_error(response.status_code, response)

    async def acomplete(self, prompt: str, model: str, **kwargs: Any) -> CompletionResponse:
        """Generate text asynchronously using the legacy OpenAI completions endpoint.

        Parameters
        ----------
        prompt : str
            Input prompt string.

        model : str
            Model name as registered in LiteLLM.

        **kwargs : Any
            Additional OpenAI completions parameters (temperature, max_tokens, etc.).
            Unknown parameters are filtered out.

        Returns:
        -------
        CompletionResponse
            Legacy completion response with id, choices, and usage.
        """
        payload: dict[str, Any] = {"model": model, "prompt": prompt}
        for k, v in kwargs.items():
            if k in self._OPENAI_COMPLETIONS_FIELDS:
                payload[k] = v
        async with ClientSession(
            headers=self.headers,
            cookies=self.cookies,
            timeout=self.async_timeout,
        ) as session:
            async with session.post(f"{self.url}/serve/completions", json=payload, ssl=self.verify) as response:
                if response.status == 200:
                    return CompletionResponse(**(await response.json()))
                else:
                    try:
                        err_body = await response.json()
                    except Exception:
                        err_body = "An error occurred with no additional information."
                    raise parse_error(response.status, err_body)

    def generate_image(self, prompt: str, model: str, **kwargs: Any) -> ImageResponse:
        """Generate images from a text prompt.

        Parameters
        ----------
        prompt : str
            Text description of the image to generate.

        model : str
            Model name as registered in LiteLLM.

        **kwargs : Any
            Additional parameters (n, size, quality, response_format, style).

        Returns:
        -------
        ImageResponse
            Image generation response with created timestamp and image data.
        """
        payload: dict[str, Any] = {"model": model, "prompt": prompt}
        for k, v in kwargs.items():
            if k in self._OPENAI_IMAGE_FIELDS:
                payload[k] = v
        response = self._session.post(f"{self.url}/serve/images/generations", json=payload)
        if response.status_code == 200:
            return ImageResponse(**response.json())
        else:
            raise parse_error(response.status_code, response)

    async def agenerate_image(self, prompt: str, model: str, **kwargs: Any) -> ImageResponse:
        """Generate images from a text prompt asynchronously.

        Parameters
        ----------
        prompt : str
            Text description of the image to generate.

        model : str
            Model name as registered in LiteLLM.

        **kwargs : Any
            Additional parameters (n, size, quality, response_format, style).

        Returns:
        -------
        ImageResponse
            Image generation response with created timestamp and image data.
        """
        payload: dict[str, Any] = {"model": model, "prompt": prompt}
        for k, v in kwargs.items():
            if k in self._OPENAI_IMAGE_FIELDS:
                payload[k] = v
        async with ClientSession(
            headers=self.headers,
            cookies=self.cookies,
            timeout=self.async_timeout,
        ) as session:
            async with session.post(f"{self.url}/serve/images/generations", json=payload, ssl=self.verify) as response:
                if response.status == 200:
                    return ImageResponse(**(await response.json()))
                else:
                    try:
                        err_body = await response.json()
                    except Exception:
                        err_body = "An error occurred with no additional information."
                    raise parse_error(response.status, err_body)

    def text_to_speech(self, text: str, model: str, voice: str = "alloy", **kwargs: Any) -> bytes:
        """Convert text to audio.

        Parameters
        ----------
        text : str
            Text to convert to speech.

        model : str
            TTS model name as registered in LiteLLM.

        voice : str
            Voice to use (default: "alloy").

        **kwargs : Any
            Additional parameters (response_format, speed).

        Returns:
        -------
        bytes
            Raw audio content.
        """
        payload: dict[str, Any] = {"model": model, "input": text, "voice": voice}
        for k, v in kwargs.items():
            if k in self._OPENAI_TTS_FIELDS:
                payload[k] = v
        response = self._session.post(f"{self.url}/serve/audio/speech", json=payload)
        if response.status_code == 200:
            return response.content
        else:
            raise parse_error(response.status_code, response)

    async def atext_to_speech(self, text: str, model: str, voice: str = "alloy", **kwargs: Any) -> bytes:
        """Convert text to audio asynchronously.

        Parameters
        ----------
        text : str
            Text to convert to speech.

        model : str
            TTS model name as registered in LiteLLM.

        voice : str
            Voice to use (default: "alloy").

        **kwargs : Any
            Additional parameters (response_format, speed).

        Returns:
        -------
        bytes
            Raw audio content.
        """
        payload: dict[str, Any] = {"model": model, "input": text, "voice": voice}
        for k, v in kwargs.items():
            if k in self._OPENAI_TTS_FIELDS:
                payload[k] = v
        async with ClientSession(
            headers=self.headers,
            cookies=self.cookies,
            timeout=self.async_timeout,
        ) as session:
            async with session.post(f"{self.url}/serve/audio/speech", json=payload, ssl=self.verify) as response:
                if response.status == 200:
                    audio_data: bytes = await response.read()
                    return audio_data
                else:
                    try:
                        err_body = await response.json()
                    except Exception:
                        err_body = "An error occurred with no additional information."
                    raise parse_error(response.status, err_body)

    def transcribe(self, file: str | bytes, model: str, filename: str = "audio.mp3", **kwargs: Any) -> dict[str, Any]:
        """Transcribe audio to text.

        Parameters
        ----------
        file : str | bytes
            Path to audio file or raw audio bytes.

        model : str
            Whisper model name as registered in LiteLLM.

        filename : str
            Filename for the upload (default: "audio.mp3").

        **kwargs : Any
            Additional parameters (language, prompt, response_format, temperature).

        Returns:
        -------
        dict[str, Any]
            Transcription response with text and metadata.
        """
        if isinstance(file, str):
            file_path = Path(file)
            if not file_path.is_file():
                raise FileNotFoundError(f"Audio file not found: {file}")
            file_data = file_path.read_bytes()
        else:
            file_data = file

        files = {"file": (filename, BytesIO(file_data))}
        data: dict[str, Any] = {"model": model}
        for k, v in kwargs.items():
            if k in self._OPENAI_TRANSCRIPTION_FIELDS:
                data[k] = v
        response = self._session.post(f"{self.url}/serve/audio/transcriptions", files=files, data=data)
        if response.status_code == 200:
            result: dict[str, Any] = response.json()
            return result
        else:
            raise parse_error(response.status_code, response)

    async def atranscribe(
        self, file: str | bytes, model: str, filename: str = "audio.mp3", **kwargs: Any
    ) -> dict[str, Any]:
        """Transcribe audio to text asynchronously.

        Parameters
        ----------
        file : str | bytes
            Path to audio file or raw audio bytes.

        model : str
            Whisper model name as registered in LiteLLM.

        filename : str
            Filename for the upload (default: "audio.mp3").

        **kwargs : Any
            Additional parameters (language, prompt, response_format, temperature).

        Returns:
        -------
        dict[str, Any]
            Transcription response with text and metadata.
        """
        if isinstance(file, str):
            file_path = Path(file)
            if not file_path.is_file():
                raise FileNotFoundError(f"Audio file not found: {file}")
            file_data = file_path.read_bytes()
        else:
            file_data = file

        form = FormData()
        form.add_field("file", BytesIO(file_data), filename=filename)
        form.add_field("model", model)
        for k, v in kwargs.items():
            if k in self._OPENAI_TRANSCRIPTION_FIELDS:
                form.add_field(k, str(v))

        async with ClientSession(
            headers=self.headers,
            cookies=self.cookies,
            timeout=self.async_timeout,
        ) as session:
            async with session.post(f"{self.url}/serve/audio/transcriptions", data=form, ssl=self.verify) as response:
                if response.status == 200:
                    result: dict[str, Any] = await response.json()
                    return result
                else:
                    try:
                        err_body = await response.json()
                    except Exception:
                        err_body = "An error occurred with no additional information."
                    raise parse_error(response.status, err_body)

    def generate(self, prompt: str, model: FoundationModel) -> Response:
        """Generate text using OpenAI-compatible chat completions endpoint.

        Parameters
        ----------
        prompt : str
            Input prompt.

        model : FoundationModel
            Foundation model for text generation.

        Returns:
        -------
        Response
            Text generation response.
        """
        payload = self._build_chat_payload(prompt, model, stream=False)
        response = self._session.post(f"{self.url}/serve/chat/completions", json=payload)
        if response.status_code == 200:
            output = response.json()
            choice = output.get("choices", [{}])[0] if output.get("choices") else {}
            usage = output.get("usage", {})
            return Response(
                generated_text=choice.get("message", {}).get("content", "") or "",
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

        Returns:
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
                if response.status == 200:
                    output = await response.json()
                    choice = output.get("choices", [{}])[0] if output.get("choices") else {}
                    usage = output.get("usage", {})
                    return Response(
                        generated_text=choice.get("message", {}).get("content", "") or "",
                        generated_tokens=usage.get("completion_tokens", 0),
                        finish_reason=choice.get("finish_reason", "stop"),
                    )
                else:
                    try:
                        err_body = await response.json()
                    except Exception:
                        err_body = "An error occurred with no additional information."
                    raise parse_error(response.status, err_body)

    def generate_stream(self, prompt: str, model: FoundationModel) -> Generator[StreamingResponse]:
        """Generate text with streaming using OpenAI-compatible SSE format.

        Parameters
        ----------
        prompt : str
            Input prompt.

        model : FoundationModel
            Foundation model for text generation.

        Returns:
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

        Returns:
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
                    try:
                        err_body = await response.json()
                    except Exception:
                        err_body = "An error occurred with no additional information."
                    raise parse_error(response.status, err_body)
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

        Returns:
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

        Returns:
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
                    try:
                        err_body = await response.json()
                    except Exception:
                        err_body = "An error occurred with no additional information."
                    raise parse_error(response.status, err_body)
                output = await response.json()
                return [item["embedding"] for item in output["data"]]

    def __del__(self) -> None:
        """Close session."""
        try:
            self._session.close()
        except Exception as e:
            logging.debug(f"Error closing session during cleanup: {e}")
