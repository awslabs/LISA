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

"""Integration tests for the LLM proxy (generate, stream, async).

Tests text generation via the LISA LiteLLM proxy against a deployed environment.
Requires: deployed LISA with at least one textgen model (any inference container).
"""

import logging

import pytest
from lisapy import LisaApi, LisaLlm
from lisapy.types import FoundationModel, ModelKwargs

logger = logging.getLogger(__name__)


def _get_textgen_model(lisa_api: LisaApi, streaming: bool = True) -> FoundationModel:
    """Get the first available textgen model via the LISA API (rich format).

    The LiteLLM REST endpoint returns bare OpenAI-compatible format without modelType/provider.
    The LISA API Gateway returns full model details needed to construct a FoundationModel.
    """
    models = lisa_api.list_models()
    for m in models:
        if m.get("modelType") != "textgen":
            continue
        if streaming and not m.get("streaming"):
            continue
        container = m.get("inferenceContainer", "vllm")
        fm = FoundationModel(
            provider=f"ecs.textgen.{container}",
            model_name=m["modelId"],
            model_type="textgen",
            model_kwargs=ModelKwargs(max_new_tokens=50),
            streaming=m.get("streaming", False),
        )
        logger.info(f"Using textgen model: {m['modelName']} (id={m['modelId']}, container={container})")
        return fm
    pytest.skip("No textgen model deployed — run `npm run test:integ:setup` first")


def test_list_textgen_models(lisa_api: LisaApi) -> None:
    """Verify that at least one textgen model is available via the LISA API."""
    models = lisa_api.list_models()
    textgen = [m for m in models if m.get("modelType") == "textgen"]
    assert len(textgen) > 0, "No textgen models found"

    for m in textgen:
        assert m.get("modelName"), "Model missing modelName"
        assert m.get("modelId"), "Model missing modelId"
        assert m.get("modelType") == "textgen"


def test_generate(lisa_api: LisaApi, lisa_llm: LisaLlm) -> None:
    """Test batch text generation from any available textgen model."""
    model = _get_textgen_model(lisa_api, streaming=False)
    model.model_kwargs = ModelKwargs(max_new_tokens=10)

    response = lisa_llm.generate("What is machine learning?", model)
    assert response.generated_text is not None
    assert response.generated_tokens > 0
    assert response.finish_reason in ("length", "stop")
    logger.info(f"Generated {response.generated_tokens} tokens, reason={response.finish_reason}")


def test_generate_stream(lisa_api: LisaApi, lisa_llm: LisaLlm) -> None:
    """Test streaming text generation — verify chunks arrive incrementally."""
    model = _get_textgen_model(lisa_api)

    responses = list(lisa_llm.generate_stream("Explain deep learning briefly.", model=model))
    assert len(responses) >= 1, "No streaming responses received"

    # At least one response should have a non-empty token
    tokens = [r.token for r in responses if r.token]
    assert len(tokens) > 0, "No non-empty tokens in stream"

    # Final response should have finish_reason set
    final = responses[-1]
    assert final.finish_reason is not None, f"Final response missing finish_reason: {final}"
    logger.info(f"Streamed {len(responses)} chunks, {len(tokens)} tokens, reason={final.finish_reason}")


@pytest.mark.asyncio
async def test_generate_async(lisa_api: LisaApi, lisa_llm: LisaLlm) -> None:
    """Test async batch text generation."""
    model = _get_textgen_model(lisa_api, streaming=False)
    model.model_kwargs = ModelKwargs(max_new_tokens=10)

    response = await lisa_llm.agenerate("What is artificial intelligence?", model=model)
    assert response.generated_text is not None
    assert response.generated_tokens > 0
    assert response.finish_reason in ("length", "stop")
    logger.info(f"Async generated {response.generated_tokens} tokens, reason={response.finish_reason}")


@pytest.mark.asyncio
async def test_generate_stream_async(lisa_api: LisaApi, lisa_llm: LisaLlm) -> None:
    """Test async streaming text generation."""
    model = _get_textgen_model(lisa_api)

    responses = []
    async for response in lisa_llm.agenerate_stream("Describe neural networks briefly.", model=model):
        responses.append(response)

    assert len(responses) >= 1, "No async streaming responses received"

    tokens = [r.token for r in responses if r.token]
    assert len(tokens) > 0, "No non-empty tokens in async stream"

    final = responses[-1]
    assert final.finish_reason is not None, f"Final response missing finish_reason: {final}"
    logger.info(f"Async streamed {len(responses)} chunks, {len(tokens)} tokens, reason={final.finish_reason}")


@pytest.mark.skip(reason="LisaLlm.describe_model() not implemented in SDK")
def test_model_not_found(lisa_llm: LisaLlm) -> None:
    """Attempts to describe a model that doesn't exist."""
    from lisapy.errors import NotFoundError

    with pytest.raises(NotFoundError):
        lisa_llm.describe_model(provider="unknown.provider", model_name="model-name")


@pytest.mark.skip(reason="Requires self-hosted TEI embedding model and SDK list_embedding_models()")
def test_embed_instructor(lisa_llm: LisaLlm) -> None:
    """Generates a simple embedding from a self-hosted embedding model."""
    embedding_models = lisa_llm.list_embedding_models()
    model = [m for m in embedding_models if m.provider == "ecs.embedding.instructor"][0]
    embedding = lisa_llm.embed("test", model)

    assert isinstance(embedding, list)
    assert isinstance(embedding[0], list)
    assert isinstance(embedding[0][0], float)
