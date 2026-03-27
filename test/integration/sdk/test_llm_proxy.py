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

"""Integration tests for the LLM proxy (LiteLLM REST API).

Tests the LiteLLM proxy endpoints via the LisaLlm SDK against a deployed environment.
Requires: deployed LISA with at least one textgen model.
"""

import logging

import pytest
from lisapy import LisaLlm
from lisapy.types import FoundationModel, ModelKwargs

logger = logging.getLogger(__name__)


def _get_textgen_model(lisa_llm: LisaLlm) -> FoundationModel:
    """Discover the first available textgen model from the proxy's model list.

    The LiteLLM REST API returns OpenAI-format model list (id, object, created).
    We use the model id directly since that's what /chat/completions accepts.
    """
    models = lisa_llm.list_models()
    if not models:
        pytest.skip("No models available on LLM proxy")

    # The proxy returns all models — we need a textgen one.
    # Since the OpenAI format doesn't include modelType, we try the first model
    # and rely on the generate call to validate it works for text generation.
    # Models like "titan-embed-all" will fail generation, so we skip known embedding patterns.
    embedding_patterns = ("embed", "embedding")
    for m in models:
        model_id = m.get("id", "")
        if not any(p in model_id.lower() for p in embedding_patterns):
            fm = FoundationModel(
                provider="",
                model_name=model_id,
                model_type="textgen",
                model_kwargs=ModelKwargs(max_new_tokens=20),
                streaming=True,
            )
            logger.info(f"Using textgen model: {model_id}")
            return fm

    pytest.skip("No textgen model found (all models appear to be embedding models)")


# ---------------------------------------------------------------------------
# Test 1: Can list models via the proxy
# ---------------------------------------------------------------------------


def test_list_models(lisa_llm: LisaLlm) -> None:
    """The LLM proxy should return at least one model."""
    models = lisa_llm.list_models()
    assert len(models) > 0, "No models returned by LLM proxy"
    for m in models:
        assert "id" in m, f"Model missing 'id' field: {m}"


# ---------------------------------------------------------------------------
# Test 2: Can generate text (non-streaming)
# ---------------------------------------------------------------------------


def test_generate(lisa_llm: LisaLlm) -> None:
    """Non-streaming chat completion should return generated text."""
    model = _get_textgen_model(lisa_llm)
    response = lisa_llm.generate("Say hello in one word.", model)

    assert response.generated_text, "No text generated"
    assert response.generated_tokens > 0, "Token count should be positive"
    assert response.finish_reason in ("stop", "length"), f"Unexpected finish_reason: {response.finish_reason}"
    logger.info(f"Generated: {response.generated_text!r} ({response.generated_tokens} tokens)")


# ---------------------------------------------------------------------------
# Test 3: Can generate text (streaming)
# ---------------------------------------------------------------------------


def test_generate_stream(lisa_llm: LisaLlm) -> None:
    """Streaming chat completion should yield incremental token chunks."""
    model = _get_textgen_model(lisa_llm)
    chunks = list(lisa_llm.generate_stream("Explain what an LLM is in one sentence.", model=model))

    assert len(chunks) >= 1, "No streaming chunks received"

    tokens = [c.token for c in chunks if c.token]
    assert len(tokens) > 0, "No non-empty tokens in stream"

    # The last chunk with finish_reason set signals completion
    finished = [c for c in chunks if c.finish_reason]
    assert len(finished) > 0, "No chunk with finish_reason received"

    logger.info(f"Streamed {len(chunks)} chunks, {len(tokens)} content tokens")


# ---------------------------------------------------------------------------
# Test 4: Can generate text (async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_async(lisa_llm: LisaLlm) -> None:
    """Async chat completion should return the same structure as sync."""
    model = _get_textgen_model(lisa_llm)
    response = await lisa_llm.agenerate("Say goodbye in one word.", model=model)

    assert response.generated_text, "No text generated (async)"
    assert response.generated_tokens > 0
    assert response.finish_reason in ("stop", "length")
    logger.info(f"Async generated: {response.generated_text!r}")


# ---------------------------------------------------------------------------
# Test 5: Can generate text (async streaming)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_stream_async(lisa_llm: LisaLlm) -> None:
    """Async streaming should yield incremental chunks like sync streaming."""
    model = _get_textgen_model(lisa_llm)

    chunks = []
    async for chunk in lisa_llm.agenerate_stream("What is Python?", model=model):
        chunks.append(chunk)

    assert len(chunks) >= 1, "No async streaming chunks received"

    tokens = [c.token for c in chunks if c.token]
    assert len(tokens) > 0, "No non-empty tokens in async stream"

    finished = [c for c in chunks if c.finish_reason]
    assert len(finished) > 0, "No chunk with finish_reason in async stream"

    logger.info(f"Async streamed {len(chunks)} chunks, {len(tokens)} content tokens")


# ---------------------------------------------------------------------------
# Skipped: SDK methods not yet implemented
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="LisaLlm.describe_model() not implemented in SDK")
def test_model_not_found(lisa_llm: LisaLlm) -> None:
    """Attempting to describe a non-existent model should raise NotFoundError."""
    from lisapy.errors import NotFoundError

    with pytest.raises(NotFoundError):
        lisa_llm.describe_model(provider="unknown.provider", model_name="model-name")
