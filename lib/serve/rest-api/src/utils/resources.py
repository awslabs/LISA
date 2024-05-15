"""
REST API resources.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""
from enum import Enum
from typing import Any, Dict, List, Optional, Union

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

    # OpenAI API Compatibility
    OPENAI_LIST_MODELS = "openai/models"
    OPENAI_COMPLETIONS = "openai/completions"
    OPENAI_CHAT_COMPLETIONS = "openai/chat/completions"


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


class OpenAIChatCompletionsRequest(BaseModel):
    """Run text generation for Chat Completions for OpenAI API.

    Additional documentation at https://platform.openai.com/docs/api-reference/chat/create
    """

    messages: List[Dict[str, str]] = Field(..., description="A list of messages comprising the conversation so far.")
    model: str = Field(..., description="ID of the model to use.")
    frequency_penalty: Optional[float] = Field(None, description="Penalty to add for text repetition.")
    logit_bias: Optional[Dict[Any, Any]] = Field(
        None, description="Modify the likelihood of specified tokens appearing in the completion."
    )
    logprobs: Optional[bool] = Field(
        False,
        description=" ".join(
            [
                "Whether to return log probabilities of the output tokens or not. If true, returns",
                "the log probabilities of each output token returned in the content of message.",
                "This option is ignored for TGI/Hugging Face models.",
            ]
        ),
    )
    top_logprobs: Optional[int] = Field(
        None,
        description=" ".join(
            [
                "An integer between 0 and 20 specifying the number of most likely tokens to return",
                "at each token position, each with an associated log probability. logprobs must be",
                "set to true if this parameter is used.",
                "This option is ignored for TGI/Hugging Face models.",
            ]
        ),
    )
    max_tokens: Optional[int] = Field(50, description="Maximum number of generated tokens.")
    n: Optional[int] = Field(
        1,
        description=" ".join(
            [
                "How many completions to generate for each prompt.",
                "This option is ignored for TGI/Hugging Face models.",
            ]
        ),
    )
    presence_penalty: Optional[float] = Field(
        0,
        description=" ".join(
            [
                "Number increasing the model's likelihood to talk about new topics.",
                "This option is ignored for TGI/Hugging Face models.",
            ]
        ),
    )
    seed: Optional[int] = Field(None, description="Random sampling seed.")
    stop: Optional[List[str]] = Field(
        default_factory=list, description="Stop generating tokens if a member of `stop` is generated."
    )
    stream: Optional[bool] = Field(
        False,
        description=" ".join(
            [
                "Whether to stream back partial progress. If set, tokens will be sent as data-only",
                "server-sent events as they become available, with the stream terminated by a",
                "data: [DONE] message.",
            ]
        ),
    )
    top_p: Optional[float] = Field(
        None,
        description=" ".join(
            [
                "If set to < 1, only the smallest set of most probable tokens with probabilities",
                "that add up to `top_p` or higher are kept for generation.",
            ]
        ),
    )
    temperature: Optional[float] = Field(None, description="Value used to divide the logits distribution.")


class OpenAICompletionsRequest(BaseModel):
    """Run text generation for Completions for OpenAI API.

    Additional documentation at https://platform.openai.com/docs/api-reference/completions
    """

    model: str = Field(..., description="ID of the model to use.")
    prompt: Any = Field(
        ...,
        description=" ".join(
            [
                "The prompt(s) to generate completions for, encoded as a string, array of strings,",
                "array of tokens, or array of token arrays.",
            ]
        ),
    )
    best_of: Optional[int] = Field(
        1,
        description=" ".join(
            [
                'Generates best_of completions server-side and returns the "best"',
                "(the one with the highest log probability per token). Results cannot be streamed.",
                "This option is ignored for TGI/Hugging Face models.",
            ]
        ),
    )
    echo: Optional[int] = Field(False, description="Whether to prepend the prompt to the generated text.")
    frequency_penalty: Optional[float] = Field(None, description="Penalty to add for text repetition.")
    logit_bias: Optional[Dict[Any, Any]] = Field(
        None,
        description=" ".join(
            [
                "Modify the likelihood of specified tokens appearing in the completion.",
                "This option is ignored for TGI/Hugging Face models.",
            ]
        ),
    )
    logprobs: Optional[int] = Field(
        None,
        description=" ".join(
            [
                "Include the log probabilities on the logprobs most likely output tokens,",
                "as well the chosen tokens. For example, if logprobs is 5, the API will",
                "return a list of the 5 most likely tokens. The API will always return the",
                "logprob of the sampled token, so there may be up to logprobs+1",
                "elements in the response.",
                "This option is ignored for TGI/Hugging Face models.",
            ]
        ),
    )
    max_tokens: Optional[int] = Field(
        50, description="The maximum number of tokens that can be generated in the completion."
    )
    n: Optional[int] = Field(
        1,
        description=" ".join(
            [
                "How many completions to generate for each prompt.",
                "This option is ignored for TGI/Hugging Face models.",
            ]
        ),
    )
    presence_penalty: Optional[float] = Field(
        0,
        description=" ".join(
            [
                "Number increasing the model's likelihood to talk about new topics.",
                "This option is ignored for TGI/Hugging Face models.",
            ]
        ),
    )
    seed: Optional[int] = Field(None, description="Random sampling seed.")
    stop: Optional[Any] = Field(
        default_factory=list, description="Stop generating tokens if a member of `stop` is generated."
    )
    stream: Optional[bool] = Field(
        False,
        description=" ".join(
            [
                "Whether to stream back partial progress.",
                "If set, tokens will be sent as data-only server-sent events as they become available,",
                "with the stream terminated by a data: [DONE] message.",
            ]
        ),
    )
    suffix: Optional[str] = Field(
        None,
        description=" ".join(
            [
                "The suffix that comes after a completion of inserted text.",
                "This parameter is only supported for gpt-3.5-turbo-instruct.",
                "This option is ignored for TGI/Hugging Face models.",
            ]
        ),
    )
    temperature: Optional[float] = Field(1.0, description="Value used to divide the logits distribution.")
    top_p: Optional[float] = Field(
        None,
        description=" ".join(
            [
                "If set to < 1, only the smallest set of most probable tokens with",
                "probabilities that add up to `top_p` or higher are kept for generation.",
            ]
        ),
    )
