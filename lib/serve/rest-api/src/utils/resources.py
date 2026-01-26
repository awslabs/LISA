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

"""REST API resources."""
from enum import Enum
from typing import Any

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
    text: str | list[str] = Field(..., description="The input text(s) to be processed by the model.")
    modelKwargs: dict[str, Any] = Field(default={}, description="Arguments to the model.")


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

    messages: list[dict[str, str]] = Field(..., description="A list of messages comprising the conversation so far.")
    model: str = Field(..., description="ID of the model to use.")
    frequency_penalty: float | None = Field(None, description="Penalty to add for text repetition.")
    logit_bias: dict[Any, Any] | None = Field(
        None, description="Modify the likelihood of specified tokens appearing in the completion."
    )
    logprobs: bool | None = Field(
        False,
        description=" ".join(
            [
                "Whether to return log probabilities of the output tokens or not. If true, returns",
                "the log probabilities of each output token returned in the content of message.",
                "This option is ignored for TGI/Hugging Face models.",
            ]
        ),
    )
    top_logprobs: int | None = Field(
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
    max_tokens: int | None = Field(50, description="Maximum number of generated tokens.")
    n: int | None = Field(
        1,
        description=" ".join(
            [
                "How many completions to generate for each prompt.",
                "This option is ignored for TGI/Hugging Face models.",
            ]
        ),
    )
    presence_penalty: float | None = Field(
        0,
        description=" ".join(
            [
                "Number increasing the model's likelihood to talk about new topics.",
                "This option is ignored for TGI/Hugging Face models.",
            ]
        ),
    )
    seed: int | None = Field(None, description="Random sampling seed.")
    stop: list[str] | None = Field(
        default_factory=list, description="Stop generating tokens if a member of `stop` is generated."
    )
    stream: bool | None = Field(
        False,
        description=" ".join(
            [
                "Whether to stream back partial progress. If set, tokens will be sent as data-only",
                "server-sent events as they become available, with the stream terminated by a",
                "data: [DONE] message.",
            ]
        ),
    )
    top_p: float | None = Field(
        None,
        description=" ".join(
            [
                "If set to < 1, only the smallest set of most probable tokens with probabilities",
                "that add up to `top_p` or higher are kept for generation.",
            ]
        ),
    )
    temperature: float | None = Field(None, description="Value used to divide the logits distribution.")


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
    best_of: int | None = Field(
        1,
        description=" ".join(
            [
                'Generates best_of completions server-side and returns the "best"',
                "(the one with the highest log probability per token). Results cannot be streamed.",
                "This option is ignored for TGI/Hugging Face models.",
            ]
        ),
    )
    echo: bool | None = Field(False, description="Whether to prepend the prompt to the generated text.")
    frequency_penalty: float | None = Field(None, description="Penalty to add for text repetition.")
    logit_bias: dict[Any, Any] | None = Field(
        None,
        description=" ".join(
            [
                "Modify the likelihood of specified tokens appearing in the completion.",
                "This option is ignored for TGI/Hugging Face models.",
            ]
        ),
    )
    logprobs: int | None = Field(
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
    max_tokens: int | None = Field(
        50, description="The maximum number of tokens that can be generated in the completion."
    )
    n: int | None = Field(
        1,
        description=" ".join(
            [
                "How many completions to generate for each prompt.",
                "This option is ignored for TGI/Hugging Face models.",
            ]
        ),
    )
    presence_penalty: float | None = Field(
        0,
        description=" ".join(
            [
                "Number increasing the model's likelihood to talk about new topics.",
                "This option is ignored for TGI/Hugging Face models.",
            ]
        ),
    )
    seed: int | None = Field(None, description="Random sampling seed.")
    stop: Any | None = Field(
        default_factory=list, description="Stop generating tokens if a member of `stop` is generated."
    )
    stream: bool | None = Field(
        False,
        description=" ".join(
            [
                "Whether to stream back partial progress.",
                "If set, tokens will be sent as data-only server-sent events as they become available,",
                "with the stream terminated by a data: [DONE] message.",
            ]
        ),
    )
    suffix: str | None = Field(
        None,
        description=" ".join(
            [
                "The suffix that comes after a completion of inserted text.",
                "This parameter is only supported for gpt-3.5-turbo-instruct.",
                "This option is ignored for TGI/Hugging Face models.",
            ]
        ),
    )
    temperature: float | None = Field(1.0, description="Value used to divide the logits distribution.")
    top_p: float | None = Field(
        None,
        description=" ".join(
            [
                "If set to < 1, only the smallest set of most probable tokens with",
                "probabilities that add up to `top_p` or higher are kept for generation.",
            ]
        ),
    )
