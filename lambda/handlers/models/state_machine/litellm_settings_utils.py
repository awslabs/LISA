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

"""Derive per-model LiteLLM params from the proxy-level ``litellmConfig``.

LISA serializes the customer's whole ``litellmConfig`` block into the
``LITELLM_CONFIG_OBJ`` env var on the model state-machine lambdas. The
create/update handlers historically copied the ENTIRE ``litellm_settings``
sub-block into each new model's ``litellm_params``.

That was incorrect: LiteLLM's ``litellm_settings`` is *proxy-scope*
(callbacks, cache, set_verbose, retries, fallbacks, ...). When those keys
land on a per-model ``litellm_params`` record they flow into the actual
completion call and are forwarded to the provider, which often rejects
them.

Real-world manifestation: setting ``litellm_settings.callbacks: ["otel"]``
in ``config-custom.yaml`` caused every newly-registered Bedrock model to
have ``callbacks`` baked into its ``litellm_params``. Older Claude models
silently ignored the unknown field, but Claude Opus 4.7 uses a strict
Pydantic-validated request schema and rejects it::

    litellm.BadRequestError: BedrockException - {"message":"The model
    returned the following errors: callbacks: Extra inputs are not
    permitted"}. Received Model Group=opus-4-7

This module owns the proxy-only blocklist and the small derivation helper
the state-machine handlers use instead of greedy inheritance.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Keys valid under ``litellm_settings`` at proxy level that MUST NOT be
# carried onto a model's ``litellm_params``. They have no per-model meaning
# and several providers reject unknown fields in their request body with
# "Extra inputs are not permitted" (Bedrock + Anthropic Opus 4.7 family,
# notably).
#
# References:
#   - https://docs.litellm.ai/docs/proxy/configs#litellm_settings
#   - https://docs.litellm.ai/docs/observability/callbacks
_PROXY_ONLY_LITELLM_SETTINGS: frozenset[str] = frozenset(
    {
        # Observability / logging
        "callbacks",
        "success_callback",
        "failure_callback",
        "service_callback",
        "turn_off_message_logging",
        "redact_messages_in_exceptions",
        "redact_user_api_key_info",
        "langfuse_default_tags",
        "json_logs",
        "set_verbose",
        # Caching (proxy-level toggles; per-model caching is configured elsewhere)
        "cache",
        "cache_params",
        "embedding_cache",
        # Router / retry / timeout defaults (per-model ``timeout`` is a separate
        # field that we deliberately leave alone here)
        "num_retries",
        "retry_after",
        "request_timeout",
        "cooldown_time",
        "allowed_fails",
        # Fallback / routing policy
        "fallbacks",
        "default_fallbacks",
        "content_policy_fallbacks",
        "context_window_fallbacks",
        # Budget / spend tracking
        "max_budget",
        "max_internal_user_budget",
        "default_max_internal_user_budget",
        "internal_user_budget_duration",
        "max_user_budget",
        "max_end_user_budget",
        "disable_end_user_cost_tracking",
        "disable_end_user_cost_tracking_prometheus_only",
        "disable_spend_logs",
        "disable_token_counter",
        # Other proxy-level toggles
        "default_team_settings",
        "default_team_disabled",
        "default_internal_user_params",
        "force_ipv4",
    }
)


def derive_per_model_litellm_params(litellm_config_obj: str | None) -> dict[str, Any]:
    """Return a safe base ``litellm_params`` dict from ``LITELLM_CONFIG_OBJ``.

    Reads the ``litellm_settings`` sub-block of the serialized
    ``litellmConfig`` env var and strips proxy-scope keys that should not
    be replicated onto each model record. Anything left is assumed to be
    a legitimate per-model override (e.g. ``drop_params``, provider auth
    overrides) and is preserved.

    Parameters
    ----------
    litellm_config_obj : str | None
        Raw JSON string from the ``LITELLM_CONFIG_OBJ`` lambda env var, or
        ``None`` / empty when unset.

    Returns
    -------
    dict[str, Any]
        Filtered settings safe to use as the starting point for a model's
        ``litellm_params``. Returns ``{}`` when the env var is missing,
        empty, not valid JSON, or has no ``litellm_settings`` sub-block.
    """
    if not litellm_config_obj:
        return {}

    try:
        parsed = json.loads(litellm_config_obj)
    except json.JSONDecodeError:
        logger.warning("LITELLM_CONFIG_OBJ is not valid JSON; treating as empty.")
        return {}

    if not isinstance(parsed, dict):
        return {}

    settings = parsed.get("litellm_settings", {})
    if not isinstance(settings, dict):
        return {}

    filtered: dict[str, Any] = {}
    dropped: list[str] = []
    for key, value in settings.items():
        if key in _PROXY_ONLY_LITELLM_SETTINGS:
            dropped.append(key)
            continue
        filtered[key] = value

    if dropped:
        logger.info(
            "Excluded proxy-only litellm_settings keys from per-model litellm_params: %s",
            sorted(dropped),
        )

    return filtered
