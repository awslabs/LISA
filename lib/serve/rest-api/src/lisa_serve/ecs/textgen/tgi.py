"""
Model adapter and kwargs validator for ECS text generation TGI model endpoints.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""
import time
import uuid
from typing import Any, AsyncGenerator, Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, confloat, Field, NonNegativeFloat, NonNegativeInt, PositiveFloat, PositiveInt
from text_generation import AsyncClient

from ...base import (
    escape_curly_brackets,
    GenerateResponse,
    GenerateStreamResponse,
    OpenAIChatCompletionsChoice,
    OpenAIChatCompletionsDelta,
    OpenAIChatCompletionsResponse,
    OpenAICompletionsChoice,
    OpenAICompletionsResponse,
    StreamTextGenModelAdapter,
    TextGenModelAdapter,
    Token,
)
from ...registry import registry


class EcsTextGenTgiValidator(BaseModel):
    """Model kwargs validator for ECS text generation TGI model endpoints.

    Parameters
    ----------
    max_new_tokens : int, default=50
        Maximum number of generated tokens.

    top_k : int, default=None
        The number of highest probability vocabulary tokens to keep for top-k-filtering.

    top_p : float, default=None
        If set to < 1, only the smallest set of most probable tokens with probabilities that add up to `top_p`
        or higher are kept for generation.

    typical_p : float, default=None
        Typical Decoding mass. See [Typical Decoding for Natural Language Generation](https://arxiv.org/abs/2202.00666)
        for more information.

    temperature : float, default=None
        Value used to divide the logits distribution.

    repetition_penalty : float, default=None
        Penalty to add for text repetition.

    return_full_text : bool, default=False
        Whether to prepend the prompt to the generated text.

    truncate : int, default=None
        Whether to truncate input tokens to given size.

    stop_sequences : List[str], default=[]
        Stop generating tokens if a member of `stop` is generated.

    seed : int, default=None
        Random sampling seed.

    do_sample : bool, default=False
        Activate logits sampling.

    watermark : bool, default=False
        Watermark output response.
    """

    max_new_tokens: NonNegativeInt = 50
    top_k: Optional[NonNegativeInt] = None
    top_p: Optional[confloat(gt=0.0, lt=1.0)] = None  # type: ignore
    typical_p: Optional[confloat(gt=0.0, lt=1.0)] = None  # type: ignore
    temperature: Optional[NonNegativeFloat] = None
    repetition_penalty: Optional[PositiveFloat] = None
    return_full_text: bool = False
    truncate: Optional[PositiveInt] = None
    stop_sequences: List[str] = Field(default_factory=list)
    seed: Optional[PositiveInt] = None
    do_sample: bool = False
    watermark: bool = False


class EcsTextGenTgiAdapter(TextGenModelAdapter, StreamTextGenModelAdapter):
    """Model adapter for ECS text generation TGI model endpoints.

    Parameters
    ----------
    model_name : str
        Model name.

    endpoint_url : str
        Endpoint URL.
    """

    def __init__(self, *, model_name: str, endpoint_url: str) -> None:
        super().__init__(model_name=model_name, endpoint_url=endpoint_url)

        # Define client
        self.client = AsyncClient(endpoint_url, timeout=60)

    async def generate(self, *, text: str, model_kwargs: Dict[str, Any]) -> GenerateResponse:  # type: ignore
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
        request = {"prompt": text, **model_kwargs}
        resp = await self.client.generate(**request)
        response = GenerateResponse(
            generatedText=resp.generated_text,
            generatedTokens=resp.details.generated_tokens,
            finishReason=resp.details.finish_reason,
        )
        logger.debug(
            f"Response: {escape_curly_brackets(response.json())}",
            extra={"event": f"{self.__class__.__name__}:generate"},
        )
        return response

    async def generate_stream(
        self, *, text: str, model_kwargs: Dict[str, Any]
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
        request = {"prompt": text, **model_kwargs}
        async for resp in self.client.generate_stream(**request):
            response = GenerateStreamResponse(
                token=Token(text=resp.token.text, special=resp.token.special),
                generatedTokens=resp.details.generated_tokens if resp.details else None,
                finishReason=resp.details.finish_reason if resp.details else None,
            )
            logger.debug(
                f"Response: {escape_curly_brackets(response.json())}",
                extra={"event": f"{self.__class__.__name__}:generate_stream"},
            )
            yield response

    async def openai_generate_stream(
        self, *, text: str, model_kwargs: Dict[str, Any], is_text_completion: bool
    ) -> AsyncGenerator[GenerateStreamResponse, None]:
        """Text generation with token streaming, conforming to the OpenAI API specification.

        Parameters
        ----------
        text : str
            Prompt input text.

        model_kwargs : Dict[str, Any]
            Arguments to text generation model.

        is_text_completion : bool
            Tells if this is a request from the /completions API (True) or if it is from the
            /chat/completions API (False)

        Returns
        -------
        AsyncGenerator[GenerateStreamResponse, None]
            Text generation model response with streaming.
        """
        request = {"prompt": text, **model_kwargs}
        resp_id = str(uuid.uuid4())
        fingerprint = str(uuid.uuid4())
        created = int(time.time())
        if is_text_completion:
            response_class = OpenAICompletionsResponse
        else:
            response_class = OpenAIChatCompletionsResponse
        async for resp in self.client.generate_stream(**request):
            response = response_class(
                id=resp_id,
                created=created,
                model=self.model_name,
                object="text_completion" if is_text_completion else "chat.completion.chunk",
                system_fingerprint=fingerprint,
                choices=[
                    OpenAICompletionsChoice(
                        index=0,
                        finish_reason=resp.details.finish_reason if resp.details else None,
                        text=resp.token.text,
                    )
                    if is_text_completion
                    else OpenAIChatCompletionsChoice(
                        index=0,
                        finish_reason=resp.details.finish_reason if resp.details else None,
                        delta=OpenAIChatCompletionsDelta(content=resp.token.text, role="assistant"),
                    )
                ],
            )
            logger.debug(
                f"Response: {escape_curly_brackets(response.json())}",
                extra={"event": f"{self.__class__.__name__}:generate_stream"},
            )
            yield response


# Register the model
registry.register(
    provider="ecs.textgen.tgi",
    adapter=EcsTextGenTgiAdapter,
    validator=EcsTextGenTgiValidator,
)
