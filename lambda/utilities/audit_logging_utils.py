"""
Shared helpers for API Gateway audit logging.

Strict opt-in behavior:
- When disabled, callers must not emit audit logs.
- When enabledPaths are provided, audit only applies when the request path
  matches one of the configured prefixes (prefix match with path-boundary).
- When auditAll is true, audit applies to all paths.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional


_DEFAULT_MAX_BODY_BYTES = 20_000

# Keys we always redact anywhere in the JSON structure.
_SENSITIVE_KEYS = {
    "password",
    "token",
    "secret",
    "apikey",
    "api_key",
    "apiKey",
    "accesskey",
    "accessKey",
    "privatekey",
    "privateKey",
}

_SENSITIVE_KEYS_LOWER = {k.lower() for k in _SENSITIVE_KEYS}

def _env_bool(name: str) -> bool:
    value = os.getenv(name, "").strip().lower()
    return value in ("1", "true", "yes", "y", "on")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def audit_enabled() -> bool:
    return _env_bool("LISA_AUDIT_ENABLED")


def audit_all() -> bool:
    # auditAll is only meaningful when auditing is enabled.
    return audit_enabled() and _env_bool("LISA_AUDIT_AUDIT_ALL")


def audit_include_json_body() -> bool:
    """
    When false (default), callers must not emit AUDIT_API_GATEWAY_REQUEST_BODY.
    CDK sets this only when audit logging is enabled and includeJsonBody is true.
    """
    return _env_bool("LISA_AUDIT_INCLUDE_JSON_BODY")


def enabled_path_prefixes() -> list[str]:
    raw = os.getenv("LISA_AUDIT_ENABLED_PATH_PREFIXES", "")
    if not raw:
        return []
    prefixes = [p.strip() for p in raw.split(",") if p.strip()]
    normalized: list[str] = []
    for p in prefixes:
        if not p.startswith("/"):
            p = f"/{p}"
        p = p.rstrip("/")
        if p:
            normalized.append(p)
    return normalized


def normalize_request_path(path: str) -> str:
    if not path:
        return "/"
    normalized = path.strip()
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    normalized = normalized.rstrip("/")
    return normalized if normalized else "/"


def strip_first_path_segment(path: str) -> str:
    # Converts "/prod/session/123" -> "/session/123"
    p = normalize_request_path(path)
    parts = [part for part in p.split("/") if part]
    if len(parts) <= 1:
        return p
    return "/" + "/".join(parts[1:])


def _path_starts_with_prefix(path: str, prefix: str) -> bool:
    if not prefix:
        return False
    if prefix == "/":
        return True

    if not path.startswith(prefix):
        return False
    if len(path) == len(prefix):
        return True
    return path[len(prefix)] == "/"


def get_matched_audit_prefix(path: str) -> Optional[str]:
    """
    Return the matched prefix (e.g. "/session") when auditing should apply.

    Returns:
        - "ALL" when auditAll is enabled
        - None when strict opt-in does not match
    """
    if not audit_enabled():
        return None
    if audit_all():
        return "ALL"

    prefixes = enabled_path_prefixes()
    if not prefixes:
        return None

    p1 = normalize_request_path(path)
    p2 = strip_first_path_segment(p1)

    for prefix in prefixes:
        if _path_starts_with_prefix(p1, prefix) or _path_starts_with_prefix(p2, prefix):
            return prefix
    return None


def should_audit_path(path: str) -> bool:
    return get_matched_audit_prefix(path) is not None


def get_method_and_path_from_method_arn(method_arn: str) -> tuple[str, str]:
    """
    Parse execute-api methodArn into (http_method, request_path).

    Example:
      arn:aws:execute-api:us-east-1:123:abc123/prod/GET/repository/foo
    """
    if not method_arn:
        return ("unknown", "/")
    try:
        # arn:...:apiId/stage/VERB/path...
        parts = method_arn.split("/")
        # parts[-1] includes part(s) of the resource path; join everything after method.
        if len(parts) < 4:
            return ("unknown", "/")
        http_method = parts[2] if len(parts) > 2 else "unknown"
        resource_path = "/".join(parts[3:]) if len(parts) > 3 else ""
        return (http_method or "unknown", normalize_request_path(resource_path))
    except Exception:
        return ("unknown", "/")


def sanitize_json_for_audit(value: Any) -> Any:
    """
    Recursively redact sensitive keys from JSON values.

    This is intentionally permissive: it redacts by key name anywhere in the structure.
    """
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for k, v in value.items():
            key = str(k)
            if key.lower() in _SENSITIVE_KEYS_LOWER:
                sanitized[key] = "<REDACTED>"
            else:
                sanitized[key] = sanitize_json_for_audit(v)
        return sanitized
    if isinstance(value, list):
        return [sanitize_json_for_audit(v) for v in value]
    return value


def sanitize_json_body_for_audit(body: Any) -> str:
    """
    Convert body into a sanitized JSON string suitable for audit logging.

    Returns placeholder strings for non-JSON or oversized bodies.
    """
    max_bytes = _env_int("LISA_AUDIT_MAX_BODY_BYTES", _DEFAULT_MAX_BODY_BYTES)
    if body is None:
        return ""
    if isinstance(body, bytes):
        try:
            raw = body.decode("utf-8")
        except UnicodeDecodeError:
            return f"<NON_UTF8_BODY, {len(body)} bytes>"
    elif isinstance(body, str):
        raw = body
    else:
        # Unexpected body type (defensive; should still avoid logging sensitive objects).
        return "<NON_STRING_BODY>"

    if not raw:
        return ""

    raw_bytes_len = len(raw.encode("utf-8"))
    if raw_bytes_len > max_bytes:
        return "<TRUNCATED_BODY>"

    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return "<NON_JSON_BODY>"

    sanitized = sanitize_json_for_audit(parsed)
    try:
        return json.dumps(sanitized)
    except TypeError:
        # Extremely defensive fallback: ensure logs never explode.
        return json.dumps(str(sanitized))

