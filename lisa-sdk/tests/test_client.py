"""
Test basic usage of the Lisapy SDK.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""

from typing import Any, Union

import pytest
from lisapy import Lisa
from lisapy.errors import NotFoundError
from lisapy.types import ModelKwargs, ModelType


@pytest.fixture(scope="session")  # type: ignore
def url(pytestconfig: pytest.Config) -> Any:
    """Get the url argument."""
    return pytestconfig.getoption("url")


@pytest.fixture(scope="session")  # type: ignore
def verify(pytestconfig: pytest.Config) -> Union[bool, Any]:
    """Get the verify argument."""
    if pytestconfig.getoption("verify") == "false":
        return False
    elif pytestconfig.getoption("verify") == "true":
        return True
    else:
        return pytestconfig.getoption("verify")


def test_list_textgen_tgi_models(url: str, verify: Union[bool, str]) -> None:
    """Test to see if we can retrieve textgen TGI models."""
    client = Lisa(url=url, verify=verify)
    models = client.list_textgen_models()

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


def test_generate_tgi(url: str, verify: Union[bool, str]) -> None:
    """Generates minimal response from textgen.tgi model in batch mode."""
    client = Lisa(url=url, verify=verify)
    text_gen_models = client.list_textgen_models()
    model = [m for m in text_gen_models if m.provider == "ecs.textgen.tgi"][0]
    model.model_kwargs.max_new_tokens = 1  # type: ignore
    response = client.generate("test", model)

    # assert response.generated_text == ''
    assert response.generated_tokens == 1
    assert response.finish_reason == "length"


def test_model_not_found(url: str, verify: Union[bool, str]) -> None:
    """Attempts to describe a model that doesn't exist."""
    client = Lisa(url=url, verify=verify)
    with pytest.raises(NotFoundError):
        client.describe_model(provider="unknown.provider", model_name="model-name")


def test_embed_instructor(url: str, verify: Union[bool, str]) -> None:
    """Generates a simple embedding from the instructor embedding model."""
    client = Lisa(url=url, verify=verify)
    embedding_models = client.list_embedding_models()
    model = [m for m in embedding_models if m.provider == "ecs.embedding.instructor"][0]
    print(model)
    embedding = client.embed("test", model)

    assert isinstance(embedding, list)
    assert isinstance(embedding[0], list)
    assert isinstance(embedding[0][0], float)


def test_generate_stream(url: str, verify: Union[bool, str]) -> None:
    """Generates a streaming response from a textgen.tgi model."""
    client = Lisa(url=url, verify=verify)
    text_gen_models = client.list_textgen_models()
    model = [m for m in text_gen_models if m.provider == "ecs.textgen.tgi"][0]
    model.model_kwargs.max_new_tokens = 1  # type: ignore
    responses = list(client.generate_stream("what is deep learning?", model=model))

    assert len(responses) == 1
    response = responses[0]

    assert response.token == ""
    assert response.finish_reason == "length"
    assert response.generated_tokens == 1


@pytest.mark.asyncio  # type: ignore
async def test_generate_async(url: str, verify: Union[bool, str]) -> None:
    """Generates a batch async response from a textgen.tgi model."""
    client = Lisa(url=url, verify=verify)
    text_gen_models = client.list_textgen_models()
    model = [m for m in text_gen_models if m.provider == "ecs.textgen.tgi"][0]
    model.model_kwargs.max_new_tokens = 1  # type: ignore
    response = await client.agenerate("test", model=model)

    assert response.finish_reason == "length"
    assert response.generated_tokens == 1


@pytest.mark.asyncio  # type: ignore
async def test_generate_stream_async(url: str, verify: Union[bool, str]) -> None:
    """Generates a streaming async response from a textgen.tgi model."""
    client = Lisa(url=url, verify=verify)
    text_gen_models = client.list_textgen_models()
    model = [m for m in text_gen_models if m.provider == "ecs.textgen.tgi"][0]
    model.model_kwargs.max_new_tokens = 1  # type: ignore
    responses = [response async for response in client.agenerate_stream("what is deep learning?", model=model)]

    assert len(responses) == 1
    response = responses[0]

    assert response.token == ""
    assert response.finish_reason == "length"
    assert response.generated_tokens == 1
