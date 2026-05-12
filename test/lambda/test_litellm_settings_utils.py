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

"""Unit tests for ``litellm_settings_utils.derive_per_model_litellm_params``."""

import json

import pytest
from models.state_machine.litellm_settings_utils import (
    _PROXY_ONLY_LITELLM_SETTINGS,
    derive_per_model_litellm_params,
)


@pytest.mark.parametrize("missing", [None, ""])
def test_returns_empty_when_env_unset(missing):
    """Empty / unset env var yields an empty dict (handler then sets defaults)."""
    assert derive_per_model_litellm_params(missing) == {}


def test_returns_empty_when_invalid_json():
    """Bad JSON does not raise; we log and treat as empty (legacy behavior)."""
    assert derive_per_model_litellm_params("not-json") == {}


def test_returns_empty_when_top_level_not_object():
    """A JSON array / scalar at the top level cannot have litellm_settings."""
    assert derive_per_model_litellm_params(json.dumps([1, 2, 3])) == {}
    assert derive_per_model_litellm_params(json.dumps("scalar")) == {}


def test_returns_empty_when_litellm_settings_missing():
    assert derive_per_model_litellm_params(json.dumps({"db_key": "sk-x"})) == {}


def test_returns_empty_when_litellm_settings_not_object():
    """A malformed ``litellm_settings`` value is treated as absent rather than raising."""
    assert derive_per_model_litellm_params(json.dumps({"litellm_settings": "oops"})) == {}


def test_preserves_per_model_safe_keys():
    """Keys that aren't on the proxy-only blocklist are carried through."""
    cfg = {
        "litellm_settings": {
            "drop_params": True,
            "max_tokens": 1024,
            "temperature": 0.2,
        }
    }
    assert derive_per_model_litellm_params(json.dumps(cfg)) == {
        "drop_params": True,
        "max_tokens": 1024,
        "temperature": 0.2,
    }


def test_strips_callbacks_otel_regression():
    """Regression: ``callbacks: ["otel"]`` must not leak onto per-model params.

    This is the original failure mode: Bedrock + Claude Opus 4.7 rejects the
    ``callbacks`` field with "Extra inputs are not permitted" when LiteLLM
    forwards it as part of the request body.
    """
    cfg = {
        "litellm_settings": {
            "callbacks": ["otel"],
            "turn_off_message_logging": False,
            "drop_params": True,
        }
    }
    result = derive_per_model_litellm_params(json.dumps(cfg))
    assert "callbacks" not in result
    assert "turn_off_message_logging" not in result
    assert result == {"drop_params": True}


def test_strips_langfuse_callback_config():
    """Langfuse-style proxy-level callback config must not leak per-model."""
    cfg = {
        "litellm_settings": {
            "callbacks": ["langfuse"],
            "success_callback": ["langfuse"],
            "failure_callback": ["langfuse"],
            "redact_messages_in_exceptions": True,
            "json_logs": True,
            "drop_params": True,
        }
    }
    result = derive_per_model_litellm_params(json.dumps(cfg))
    assert result == {"drop_params": True}


@pytest.mark.parametrize(
    "proxy_only_key,sample_value",
    [
        ("callbacks", ["otel"]),
        ("success_callback", ["langfuse"]),
        ("failure_callback", ["s3"]),
        ("service_callback", ["datadog"]),
        ("turn_off_message_logging", False),
        ("set_verbose", True),
        ("cache", True),
        ("cache_params", {"type": "redis"}),
        ("embedding_cache", True),
        ("num_retries", 3),
        ("retry_after", 5),
        ("request_timeout", 600),
        ("fallbacks", [{"model-a": ["model-b"]}]),
        ("default_fallbacks", ["model-b"]),
        ("context_window_fallbacks", [{"model-a": ["model-b"]}]),
        ("max_budget", 100),
        ("disable_spend_logs", True),
    ],
)
def test_strips_each_proxy_only_key(proxy_only_key, sample_value):
    """Spot-check every proxy-only key on the blocklist."""
    cfg = {
        "litellm_settings": {
            "drop_params": True,
            proxy_only_key: sample_value,
        }
    }
    result = derive_per_model_litellm_params(json.dumps(cfg))
    assert proxy_only_key not in result
    assert result["drop_params"] is True


def test_blocklist_contains_callbacks():
    """Sanity check on the blocklist constant — guards against accidental edits."""
    assert "callbacks" in _PROXY_ONLY_LITELLM_SETTINGS
    assert "turn_off_message_logging" in _PROXY_ONLY_LITELLM_SETTINGS
    assert "drop_params" not in _PROXY_ONLY_LITELLM_SETTINGS


def test_does_not_mutate_input_object():
    """Caller's parsed dict should be unaffected if they re-serialize the env var."""
    cfg = {"litellm_settings": {"callbacks": ["otel"], "drop_params": True}}
    raw = json.dumps(cfg)
    derive_per_model_litellm_params(raw)
    # Re-parse and confirm callbacks is still present in the original payload.
    reparsed = json.loads(raw)
    assert reparsed["litellm_settings"]["callbacks"] == ["otel"]
