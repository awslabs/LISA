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

"""Test basic usage of the Lisapy SDK."""

import pytest
from lisapy import LisaLlm
from lisapy.errors import NotFoundError
from lisapy.types import ModelKwargs, ModelType


@pytest.mark.skip(reason="Model not deployed")
def test_list_textgen_tgi_models(lisa_llm: LisaLlm) -> None:
    """Test to see if we can retrieve textgen TGI models."""
    models = lisa_llm.list_textgen_models()

    assert all(m.model_type == ModelType.TEXTGEN for m in models)
    assert all(hasattr(m, "streaming") for m in models)

    tgi_models = [m for m in models if m.provider == "ecs.textgen.tgi"]
    tgi_model = tgi_models[0]

    assert isinstance(tgi_model.model_kwargs, ModelKwargs)
    assert hasattr(tgi_model.model_kwargs, "max_new_tokens")
    assert hasattr(tgi_model.model_kwargs, "top_k")
    assert hasattr(tgi_model.model_kwargs, "top_p")
    assert hasattr(tgi_model.model_kwargs, "do_sample")
    assert hasattr(tgi_model.model_kwargs, "temperature")
    assert hasattr(tgi_model.model_kwargs, "repetition_penalty")
    assert hasattr(tgi_model.model_kwargs, "return_full_text")
    assert hasattr(tgi_model.model_kwargs, "truncate")
    assert hasattr(tgi_model.model_kwargs, "stop_sequences")
    assert hasattr(tgi_model.model_kwargs, "seed")
    assert hasattr(tgi_model.model_kwargs, "do_sample")
    assert hasattr(tgi_model.model_kwargs, "watermark")


@pytest.mark.skip(reason="Model not deployed")
def test_generate_tgi(lisa_llm: LisaLlm) -> None:
    """Generates minimal response from textgen.tgi model in batch mode."""
    text_gen_models = lisa_llm.list_textgen_models()
    model = [m for m in text_gen_models if m.provider == "ecs.textgen.tgi"][0]
    model.model_kwargs.max_new_tokens = 1
    response = lisa_llm.generate("test", model)

    # assert response.generated_text == ''
    assert response.generated_tokens == 1
    assert response.finish_reason == "length"


@pytest.mark.skip(reason="Use API Gateway")
def test_model_not_found(lisa_llm: LisaLlm) -> None:
    """Attempts to describe a model that doesn't exist."""
    with pytest.raises(NotFoundError):
        lisa_llm.describe_model(provider="unknown.provider", model_name="model-name")


@pytest.mark.skip(reason="Model not deployed")
def test_embed_instructor(lisa_llm: LisaLlm) -> None:
    """Generates a simple embedding from the instructor embedding model."""
    embedding_models = lisa_llm.list_embedding_models()
    model = [m for m in embedding_models if m.provider == "ecs.embedding.instructor"][0]
    print(model)
    embedding = lisa_llm.embed("test", model)

    assert isinstance(embedding, list)
    assert isinstance(embedding[0], list)
    assert isinstance(embedding[0][0], float)


@pytest.mark.skip(reason="TODO")
def test_generate_stream(lisa_llm: LisaLlm) -> None:
    """Generates a streaming response from a textgen.tgi model."""
    text_gen_models = lisa_llm.list_textgen_models()
    model = [m for m in text_gen_models if m.provider == "ecs.textgen.tgi"][0]
    model.model_kwargs.max_new_tokens = 1
    responses = list(lisa_llm.generate_stream("what is deep learning?", model=model))

    assert len(responses) == 1
    response = responses[0]

    assert response.token == ""
    assert response.finish_reason == "length"
    assert response.generated_tokens == 1


@pytest.mark.asyncio
@pytest.mark.skip(reason="TODO")
async def test_generate_async(lisa_llm: LisaLlm) -> None:
    """Generates a batch async response from a textgen.tgi model."""
    text_gen_models = lisa_llm.list_textgen_models()
    model = [m for m in text_gen_models if m.provider == "ecs.textgen.tgi"][0]
    model.model_kwargs.max_new_tokens = 1
    response = await lisa_llm.agenerate("test", model=model)

    assert response.finish_reason == "length"
    assert response.generated_tokens == 1


@pytest.mark.asyncio
@pytest.mark.skip(reason="TODO")
async def test_generate_stream_async(lisa_llm: LisaLlm) -> None:
    """Generates a streaming async response from a textgen.tgi model."""
    text_gen_models = lisa_llm.list_textgen_models()
    model = [m for m in text_gen_models if m.provider == "ecs.textgen.tgi"][0]
    model.model_kwargs.max_new_tokens = 1
    responses = [response async for response in lisa_llm.agenerate_stream("what is deep learning?", model=model)]

    assert len(responses) == 1
    response = responses[0]

    assert response.token == ""
    assert response.finish_reason == "length"
    assert response.generated_tokens == 1
