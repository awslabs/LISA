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

import json
import logging
import os
from io import StringIO

from utilities.audit_logging_utils import (
    audit_include_json_body,
    get_matched_audit_prefix,
    log_audit_event,
    sanitize_json_body_for_audit,
)

# Prevent lambda/models imports from failing during autouse fixtures.
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("MODEL_TABLE_NAME", "model-table")
os.environ.setdefault("GUARDRAILS_TABLE_NAME", "guardrails-table")


def test_audit_opt_in_prefix_matching(monkeypatch):
    monkeypatch.setenv("LISA_AUDIT_ENABLED", "true")
    monkeypatch.setenv("LISA_AUDIT_AUDIT_ALL", "false")
    monkeypatch.setenv("LISA_AUDIT_ENABLED_PATH_PREFIXES", "/session,/repository")

    assert get_matched_audit_prefix("/session") == "/session"
    assert get_matched_audit_prefix("/session/123") == "/session"
    assert get_matched_audit_prefix("/prod/session/123") == "/session"

    # Prefix boundary check: should not match "/sessionfoo"
    assert get_matched_audit_prefix("/sessionfoo") is None


def test_log_audit_event_puts_json_in_message():
    """CloudWatch only shows the log message; payload must be serialized there."""
    stream = StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(message)s"))
    lg = logging.getLogger("audit_log_audit_event_test")
    lg.handlers.clear()
    lg.addHandler(handler)
    lg.setLevel(logging.INFO)
    lg.propagate = False

    log_audit_event(
        lg,
        "AUDIT_API_GATEWAY_REQUEST",
        {
            "area": "/session",
            "action": "PUT /session/x",
            "decision": "Allow",
            "user": {"username": "alice", "auth_type": "jwt"},
        },
    )
    line = stream.getvalue().strip()
    assert line.startswith("AUDIT_API_GATEWAY_REQUEST ")
    payload = json.loads(line.removeprefix("AUDIT_API_GATEWAY_REQUEST ").strip())
    assert payload["event_type"] == "AUDIT_API_GATEWAY_REQUEST"
    assert payload["area"] == "/session"
    assert payload["decision"] == "Allow"
    assert payload["user"]["username"] == "alice"


def test_audit_include_json_body_default_false(monkeypatch):
    monkeypatch.delenv("LISA_AUDIT_INCLUDE_JSON_BODY", raising=False)
    assert audit_include_json_body() is False


def test_audit_include_json_body_true(monkeypatch):
    monkeypatch.setenv("LISA_AUDIT_INCLUDE_JSON_BODY", "true")
    assert audit_include_json_body() is True


def test_audit_all_overrides_enabled_paths(monkeypatch):
    monkeypatch.setenv("LISA_AUDIT_ENABLED", "true")
    monkeypatch.setenv("LISA_AUDIT_AUDIT_ALL", "true")
    monkeypatch.setenv("LISA_AUDIT_ENABLED_PATH_PREFIXES", "")

    assert get_matched_audit_prefix("/anything") == "ALL"


def test_sanitize_json_body_for_audit_redacts_keys(monkeypatch):
    monkeypatch.setenv("LISA_AUDIT_MAX_BODY_BYTES", "10000")

    body = json.dumps(
        {
            "password": "secret-password",
            "nested": {"api_key": "secret-api-key", "other": 1},
            "token": "secret-token",
        }
    )

    sanitized_raw = sanitize_json_body_for_audit(body)
    sanitized = json.loads(sanitized_raw)

    assert sanitized["password"] == "<REDACTED>"
    assert sanitized["token"] == "<REDACTED>"
    assert sanitized["nested"]["api_key"] == "<REDACTED>"
    assert sanitized["nested"]["other"] == 1


def test_sanitize_json_body_for_audit_oversize(monkeypatch):
    monkeypatch.setenv("LISA_AUDIT_MAX_BODY_BYTES", "10")
    assert sanitize_json_body_for_audit(json.dumps({"a": "1234567890"})) == "<TRUNCATED_BODY>"


def test_sanitize_json_body_for_audit_non_json(monkeypatch):
    monkeypatch.setenv("LISA_AUDIT_MAX_BODY_BYTES", "1000")
    assert sanitize_json_body_for_audit("not json") == "<NON_JSON_BODY>"
