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
