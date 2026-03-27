"""Shared helpers for state machine failure-event parsing."""

import json
from typing import Any


def extract_model_failure_details(event: dict[str, Any], default_reason: str) -> tuple[str | None, str]:
    """Extract model id and failure reason from Step Functions catch payloads."""
    raw_error = event.get("error")
    catch_error: dict[str, Any] = raw_error if isinstance(raw_error, dict) else {}
    cause_payload = event.get("Cause") or catch_error.get("Cause")

    cause_data: dict[str, Any] | None = None
    if isinstance(cause_payload, str):
        try:
            parsed = json.loads(cause_payload)
            if isinstance(parsed, dict):
                cause_data = parsed
        except Exception:
            cause_data = None

    model_id = event.get("model_id") or event.get("modelId")
    if not model_id and isinstance(cause_data, dict):
        model_id = cause_data.get("model_id") or cause_data.get("modelId")
        if not model_id:
            cause_input = cause_data.get("input")
            if isinstance(cause_input, dict):
                model_id = cause_input.get("model_id") or cause_input.get("modelId")

    error_reason = default_reason
    if isinstance(cause_data, dict):
        error_reason = str(cause_data.get("errorMessage", error_reason))
    elif cause_payload is not None:
        error_reason = str(cause_payload)
    elif "error" in event:
        error_reason = str(event.get("error"))

    return model_id, error_reason
