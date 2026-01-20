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

"""Middleware for logging all incoming requests to FastAPI applications."""

import json
import logging
import time
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware, Request, RequestResponseEndpoint, Response
from utilities.header_sanitizer import sanitize_headers

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that logs all incoming requests with sanitized data.

    This middleware provides:
    - Automatic logging of all requests (method, path, headers, params)
    - Header sanitization (redacts auth, replaces user-controlled headers)
    - Request timing (duration in milliseconds)
    - User context extraction (username, groups, auth type)
    - Correlation IDs for request tracing

    Security features:
    - Authorization headers are redacted
    - User-controlled headers (x-forwarded-for) replaced with server values
    - Real client IP extracted from API Gateway context
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Process the request, log details, and pass to next handler.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or handler in the chain

        Returns:
            Response from the next handler
        """
        # Start timing
        start_time = time.time()

        # Extract AWS event from request scope (set by AWSAPIGatewayMiddleware)
        event = request.scope.get("aws.event", {})

        # Build sanitized request data for logging
        log_data = self._build_log_data(request, event)

        # Log the incoming request
        logger.info(
            f"Request: {request.method} {request.url.path}",
            extra=log_data,
        )

        # Process the request
        response = await call_next(request)

        # Calculate request duration
        duration_ms = (time.time() - start_time) * 1000

        # Log the response
        logger.info(
            f"Response: {request.method} {request.url.path} - {response.status_code} ({duration_ms:.2f}ms)",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "request_id": event.get("requestContext", {}).get("requestId"),
            },
        )

        return response

    def _build_log_data(self, request: Request, event: dict[str, Any]) -> dict[str, Any]:
        """
        Build sanitized log data from request and AWS event.

        Args:
            request: The FastAPI request object
            event: The AWS Lambda event (from API Gateway)

        Returns:
            Dictionary with sanitized request data for logging
        """
        # Extract request context
        request_context = event.get("requestContext", {})
        authorizer = request_context.get("authorizer", {})
        identity = request_context.get("identity", {})

        # Sanitize headers (redact auth, replace user-controlled headers)
        raw_headers = dict(request.headers)
        sanitized_headers = sanitize_headers(raw_headers, event)

        # Build log data
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": sanitized_headers,
            "request_id": request_context.get("requestId"),
            "source_ip": identity.get("sourceIp"),  # Real IP from API Gateway
            "user_agent": identity.get("userAgent"),
            "user": {
                "username": authorizer.get("username"),
                "groups": authorizer.get("groups", []),
                "auth_type": authorizer.get("authType"),
            },
        }

        # Add path parameters if present
        if hasattr(request, "path_params") and request.path_params:
            log_data["path_params"] = dict(request.path_params)

        return log_data

    def _sanitize_body(self, body: bytes) -> str:
        """
        Sanitize request body for logging.

        Attempts to parse as JSON and redact sensitive fields.
        If parsing fails, returns a placeholder.

        Args:
            body: Raw request body bytes

        Returns:
            Sanitized body as string
        """
        if not body:
            return ""

        try:
            # Try to parse as JSON
            body_json = json.loads(body)

            # Redact sensitive fields
            sensitive_fields = ["password", "token", "secret", "apiKey", "api_key"]
            for field in sensitive_fields:
                if field in body_json:
                    body_json[field] = "<REDACTED>"

            return json.dumps(body_json)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Not JSON or can't decode - return placeholder
            return f"<binary data, {len(body)} bytes>"
