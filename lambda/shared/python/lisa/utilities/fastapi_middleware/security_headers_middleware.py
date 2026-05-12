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

"""Middleware for adding security headers to all FastAPI responses."""

from starlette.middleware.base import BaseHTTPMiddleware, Request, RequestResponseEndpoint, Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds security headers to all HTTP responses.

    Security headers included:
    - Strict-Transport-Security: Forces HTTPS connections
    - X-Content-Type-Options: Prevents MIME sniffing attacks
    - X-Frame-Options: Prevents clickjacking attacks
    - Cache-Control: Prevents caching of sensitive data
    - Pragma: Legacy cache control for HTTP/1.0
    - Content-Type: Ensures JSON responses are properly typed

    These headers protect against common web vulnerabilities and ensure
    secure communication between client and server.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Process the request and add security headers to the response.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware or handler in the chain

        Returns:
            Response with security headers added
        """
        # Call the next handler to get the response
        response = await call_next(request)

        # Add security headers to the response
        # HSTS: Force HTTPS for 547 days (47304000 seconds) including subdomains
        response.headers["Strict-Transport-Security"] = "max-age=47304000; includeSubDomains"

        # Prevent MIME sniffing (forces browser to respect Content-Type)
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Prevent clickjacking by disallowing iframe embedding
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent caching of sensitive data
        response.headers["Cache-Control"] = "no-store, no-cache"
        response.headers["Pragma"] = "no-cache"

        # Ensure Content-Type is set (FastAPI usually sets this, but we ensure it)
        if "Content-Type" not in response.headers:
            response.headers["Content-Type"] = "application/json"

        return response
