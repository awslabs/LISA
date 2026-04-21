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
from lisapy.types import CompletionResponse, FoundationModel, ModelInfoEntry, ModelKwargs

logger = logging.getLogger(__name__)


_NON_TEXTGEN_MODES = frozenset({"embedding", "image_generation", "audio_speech", "audio_transcription", "rerank"})
_NON_TEXTGEN_PATTERNS = ("embed", "embedding", "rerank")


def _get_textgen_model(lisa_llm: LisaLlm) -> FoundationModel:
    """Discover the first available textgen model using the model/info endpoint.

    Uses get_model_info() which returns the full LiteLLM model database including
    model_info.mode (e.g. "chat", "embedding") for reliable model type detection.
    Falls back to name-based heuristics if mode is not available.
    """
    try:
        entries = lisa_llm.get_model_info()
    except Exception as e:
        logger.warning(f"get_model_info() failed, falling back to list_models(): {e}")
        entries = []

    for entry in entries:
        mode = entry.model_info.get("mode", "")
        if mode and mode in _NON_TEXTGEN_MODES:
            continue
        if not mode and any(p in entry.model_name.lower() for p in _NON_TEXTGEN_PATTERNS):
            continue
        fm = FoundationModel(
            provider="",
            model_name=entry.model_name,
            model_type="textgen",
            model_kwargs=ModelKwargs(max_new_tokens=20),
            streaming=True,
        )
        logger.info(
            f"Using textgen model: {entry.model_name} (mode={mode!r}, "
            f"litellm_model={entry.litellm_params.get('model', 'N/A')})"
        )
        return fm

    # Fallback: try list_models() with name-based heuristic if model/info failed
    models = lisa_llm.list_models()
    if not models:
        pytest.skip("No models available on LLM proxy")

    for m in models:
        model_id = m.get("id", "")
        if not any(p in model_id.lower() for p in _NON_TEXTGEN_PATTERNS):
            fm = FoundationModel(
                provider="",
                model_name=model_id,
                model_type="textgen",
                model_kwargs=ModelKwargs(max_new_tokens=20),
                streaming=True,
            )
            logger.info(f"Using textgen model (fallback): {model_id}")
            return fm

    pytest.skip("No textgen model found (all models appear to be non-textgen)")


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
# Test 6: Health check
# ---------------------------------------------------------------------------


def test_health(lisa_llm: LisaLlm) -> None:
    """Basic health check should return a response without error."""
    result = lisa_llm.health()
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    logger.info(f"Health check response: {result}")


# ---------------------------------------------------------------------------
# Test 7: Health readiness
# ---------------------------------------------------------------------------


def test_health_readiness(lisa_llm: LisaLlm) -> None:
    """Readiness check should return a response without error."""
    result = lisa_llm.health_readiness()
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    logger.info(f"Health readiness response: {result}")


# ---------------------------------------------------------------------------
# Test 8: Health liveliness
# ---------------------------------------------------------------------------


def test_health_liveliness(lisa_llm: LisaLlm) -> None:
    """Liveliness check should return a normalized dict response."""
    result = lisa_llm.health_liveliness()
    assert isinstance(result, dict), f"Expected dict, got {type(result)}"
    assert "status" in result, f"Expected 'status' key in response: {result}"
    logger.info(f"Health liveliness response: {result}")


# ---------------------------------------------------------------------------
# Test 9: Get model info
# ---------------------------------------------------------------------------


def test_get_model_info(lisa_llm: LisaLlm) -> None:
    """Model info endpoint should return a list of ModelInfoEntry objects."""

    result = lisa_llm.get_model_info()
    assert isinstance(result, list), f"Expected list, got {type(result)}"
    if not result:
        pytest.skip("model/info returned empty list — cannot validate ModelInfoEntry fields")
    assert isinstance(result[0], ModelInfoEntry), f"Expected ModelInfoEntry, got {type(result[0])}"
    assert result[0].model_name, "Model name should not be empty"
    logger.info(f"Found {len(result)} models via model/info")
    for entry in result[:3]:
        logger.info(f"  - {entry.model_name}: {list(entry.litellm_params.keys())}")


# ---------------------------------------------------------------------------
# Test 10: Legacy text completions
# ---------------------------------------------------------------------------


def test_complete(lisa_llm: LisaLlm) -> None:
    """Legacy completions endpoint should return a CompletionResponse."""

    model = _get_textgen_model(lisa_llm)
    try:
        result = lisa_llm.complete(
            "Once upon a time",
            model=model.model_name,
            max_tokens=20,
            temperature=0.0,
        )
    except Exception as e:
        pytest.skip(f"Model {model.model_name} does not support legacy /completions: {e}")

    assert isinstance(result, CompletionResponse), f"Expected CompletionResponse, got {type(result)}"
    assert result.id, "Completion ID should not be empty"
    assert len(result.choices) > 0, "Should have at least one choice"
    assert result.choices[0].text, "Generated text should not be empty"
    logger.info(f"Completion: {result.choices[0].text!r} (finish_reason={result.choices[0].finish_reason})")
