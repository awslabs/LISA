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

"""Tests for request middleware."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the REST API source to the path
rest_api_src = Path(__file__).parent.parent.parent / "lib" / "serve" / "rest-api" / "src"
sys.path.insert(0, str(rest_api_src))


class TestRequestMiddleware:
    """Tests for request processing middleware."""

    @pytest.mark.asyncio
    async def test_process_request_success(self):
        """Test successful request processing."""
        from fastapi import Response
        from middleware.request_middleware import process_request_middleware

        # Create mock request and real response
        mock_request = MagicMock()
        mock_request.url.path = "/test"

        mock_response = Response(content="test", status_code=200)

        async def mock_call_next(request):
            return mock_response

        # Process the request
        result = await process_request_middleware(mock_request, mock_call_next)

        # Verify response has request ID header
        assert "X-Request-ID" in result.headers
        assert result == mock_response

    @pytest.mark.asyncio
    async def test_process_request_with_exception(self):
        """Test request processing when handler raises exception."""
        from fastapi.responses import JSONResponse
        from middleware.request_middleware import process_request_middleware

        # Create mock request
        mock_request = MagicMock()
        mock_request.url.path = "/test"

        async def mock_call_next_error(request):
            raise ValueError("Test error")

        # Process the request
        result = await process_request_middleware(mock_request, mock_call_next_error)

        # Verify error response
        assert isinstance(result, JSONResponse)
        assert result.status_code == 500
        assert "X-Request-ID" in result.headers

    @pytest.mark.asyncio
    async def test_process_request_adds_unique_id(self):
        """Test that each request gets a unique ID."""
        from fastapi import Response
        from middleware.request_middleware import process_request_middleware

        mock_request = MagicMock()
        mock_request.url.path = "/test"

        mock_response1 = Response(content="test1", status_code=200)
        mock_response2 = Response(content="test2", status_code=200)

        async def mock_call_next1(request):
            return mock_response1

        async def mock_call_next2(request):
            return mock_response2

        # Process two requests
        result1 = await process_request_middleware(mock_request, mock_call_next1)
        result2 = await process_request_middleware(mock_request, mock_call_next2)

        # Verify different request IDs
        assert result1.headers["X-Request-ID"] != result2.headers["X-Request-ID"]

    @pytest.mark.asyncio
    async def test_process_request_logs_timing(self):
        """Test that request timing is logged."""
        from fastapi import Response
        from middleware.request_middleware import process_request_middleware

        mock_request = MagicMock()
        mock_request.url.path = "/test"

        mock_response = Response(content="test", status_code=200)

        async def mock_call_next(request):
            return mock_response

        with patch("middleware.request_middleware.logger") as mock_logger:
            await process_request_middleware(mock_request, mock_call_next)

            # Verify logging was called
            assert mock_logger.contextualize.called
            assert mock_logger.bind.called
