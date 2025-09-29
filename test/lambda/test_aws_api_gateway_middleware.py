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

"""Tests for AWS API Gateway middleware."""

from unittest.mock import AsyncMock, Mock

from fastapi import FastAPI
from utilities.fastapi_middleware.aws_api_gateway_middleware import AWSAPIGatewayMiddleware


class TestAWSAPIGatewayMiddleware:
    """Test cases for AWS API Gateway middleware."""

    def test_middleware_initialization(self):
        """Test middleware initialization."""
        app = FastAPI()
        middleware = AWSAPIGatewayMiddleware(app)

        assert middleware.app == app

    def test_dispatch_with_existing_root_path(self):
        """Test dispatch when root_path is already set."""
        app = FastAPI()
        middleware = AWSAPIGatewayMiddleware(app)

        # Mock request with existing root_path
        request = Mock()
        request.scope = {"root_path": "/existing"}
        request.app = app

        # Mock call_next
        call_next = AsyncMock()
        call_next.return_value = Mock()

        # Mock response
        response = Mock()
        call_next.return_value = response

        # Run the middleware
        import asyncio

        result = asyncio.run(middleware.dispatch(request, call_next))

        assert result == response
        call_next.assert_called_once_with(request)

    def test_dispatch_with_aws_event_default_stage(self):
        """Test dispatch with AWS event and default stage."""
        app = FastAPI()
        middleware = AWSAPIGatewayMiddleware(app)

        # Mock request with AWS event and default stage
        request = Mock()
        request.scope = {
            "root_path": "",
            "aws.event": {
                "pathParameters": {"proxy": "test"},
                "requestContext": {"stage": "$default", "path": "/test"},
            },
        }
        request.app = app

        # Mock call_next
        call_next = AsyncMock()
        call_next.return_value = Mock()

        # Run the middleware
        import asyncio

        result = asyncio.run(middleware.dispatch(request, call_next))

        assert result is not None
        call_next.assert_called_once_with(request)

    def test_dispatch_with_aws_event_custom_stage(self):
        """Test dispatch with AWS event and custom stage."""
        app = FastAPI()
        middleware = AWSAPIGatewayMiddleware(app)

        # Mock request with AWS event and custom stage
        request = Mock()
        request.scope = {
            "root_path": "",
            "aws.event": {
                "pathParameters": {"proxy": "test"},
                "requestContext": {"stage": "dev", "path": "/dev/test"},
                "path": "/test",
            },
        }
        request.app = app

        # Mock call_next
        call_next = AsyncMock()
        call_next.return_value = Mock()

        # Run the middleware
        import asyncio

        result = asyncio.run(middleware.dispatch(request, call_next))

        assert result is not None
        call_next.assert_called_once_with(request)
        assert middleware.app.root_path == "/dev"
        assert request.scope["root_path"] == "/dev"

    def test_dispatch_with_docs_path(self):
        """Test dispatch with /docs path."""
        app = FastAPI()
        middleware = AWSAPIGatewayMiddleware(app)

        # Mock request with /docs path
        request = Mock()
        request.scope = {
            "root_path": "",
            "aws.event": {
                "pathParameters": {"proxy": "test"},
                "requestContext": {"stage": "dev", "path": "/dev/docs"},
                "path": "/docs",
            },
        }
        request.app = app

        # Mock call_next
        call_next = AsyncMock()
        call_next.return_value = Mock()

        # Run the middleware
        import asyncio

        result = asyncio.run(middleware.dispatch(request, call_next))

        assert result is not None
        call_next.assert_called_once_with(request)

    def test_dispatch_with_stage_path_starting_with_stage(self):
        """Test dispatch when request path starts with stage path."""
        app = FastAPI()
        middleware = AWSAPIGatewayMiddleware(app)

        # Mock request with path starting with stage
        request = Mock()
        request.scope = {
            "root_path": "",
            "aws.event": {
                "pathParameters": {"proxy": "test"},
                "requestContext": {"stage": "dev", "path": "/dev/test"},
                "path": "/test",
            },
        }
        request.app = app

        # Mock call_next
        call_next = AsyncMock()
        call_next.return_value = Mock()

        # Run the middleware
        import asyncio

        result = asyncio.run(middleware.dispatch(request, call_next))

        assert result is not None
        call_next.assert_called_once_with(request)
        assert request.app.openapi_url == "/dev/openapi.json"

    def test_dispatch_without_aws_event(self):
        """Test dispatch without AWS event in scope."""
        app = FastAPI()
        middleware = AWSAPIGatewayMiddleware(app)

        # Mock request without AWS event
        request = Mock()
        request.scope = {"root_path": ""}
        request.app = app

        # Mock call_next
        call_next = AsyncMock()
        call_next.return_value = Mock()

        # Run the middleware
        import asyncio

        result = asyncio.run(middleware.dispatch(request, call_next))

        assert result is not None
        call_next.assert_called_once_with(request)
