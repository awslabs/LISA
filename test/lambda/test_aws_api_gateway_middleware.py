"""
Refactored tests for AWS API Gateway middleware using fixture-based mocking.
Replaces direct mocks with proper fixtures for better test isolation and consistency.
"""

import pytest
from unittest.mock import AsyncMock, Mock
import sys
import os
import asyncio

# Add lambda directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "lambda"))


@pytest.fixture
def mock_aws_api_gateway_middleware_common():
    """Common mocks for AWS API Gateway middleware tests."""
    yield


@pytest.fixture
def aws_api_gateway_middleware_classes():
    """Import AWS API Gateway middleware classes."""
    from fastapi import FastAPI
    from utilities.fastapi_middleware.aws_api_gateway_middleware import AWSAPIGatewayMiddleware
    return {
        'FastAPI': FastAPI,
        'AWSAPIGatewayMiddleware': AWSAPIGatewayMiddleware
    }


@pytest.fixture
def sample_app(aws_api_gateway_middleware_classes):
    """Sample FastAPI application."""
    return aws_api_gateway_middleware_classes['FastAPI']()


@pytest.fixture
def middleware_instance(aws_api_gateway_middleware_classes, sample_app):
    """AWS API Gateway middleware instance."""
    return aws_api_gateway_middleware_classes['AWSAPIGatewayMiddleware'](sample_app)


@pytest.fixture
def mock_request():
    """Mock request object."""
    request = Mock()
    request.app = Mock()
    return request


@pytest.fixture
def mock_call_next():
    """Mock call_next function."""
    call_next = AsyncMock()
    call_next.return_value = Mock()
    return call_next


@pytest.fixture
def sample_request_with_existing_root_path(mock_request, sample_app):
    """Sample request with existing root_path."""
    mock_request.scope = {"root_path": "/existing"}
    mock_request.app = sample_app
    return mock_request


@pytest.fixture
def sample_request_with_aws_event_default_stage(mock_request, sample_app):
    """Sample request with AWS event and default stage."""
    mock_request.scope = {
        "root_path": "",
        "aws.event": {
            "pathParameters": {"proxy": "test"},
            "requestContext": {"stage": "$default", "path": "/test"},
        },
    }
    mock_request.app = sample_app
    return mock_request


@pytest.fixture
def sample_request_with_aws_event_custom_stage(mock_request, sample_app):
    """Sample request with AWS event and custom stage."""
    mock_request.scope = {
        "root_path": "",
        "aws.event": {
            "pathParameters": {"proxy": "test"},
            "requestContext": {"stage": "dev", "path": "/dev/test"},
            "path": "/test",
        },
    }
    mock_request.app = sample_app
    return mock_request


@pytest.fixture
def sample_request_with_docs_path(mock_request, sample_app):
    """Sample request with /docs path."""
    mock_request.scope = {
        "root_path": "",
        "aws.event": {
            "pathParameters": {"proxy": "test"},
            "requestContext": {"stage": "dev", "path": "/dev/docs"},
            "path": "/docs",
        },
    }
    mock_request.app = sample_app
    return mock_request


@pytest.fixture
def sample_request_with_stage_path(mock_request, sample_app):
    """Sample request with path starting with stage."""
    mock_request.scope = {
        "root_path": "",
        "aws.event": {
            "pathParameters": {"proxy": "test"},
            "requestContext": {"stage": "dev", "path": "/dev/test"},
            "path": "/test",
        },
    }
    mock_request.app = sample_app
    return mock_request


@pytest.fixture
def sample_request_without_aws_event(mock_request, sample_app):
    """Sample request without AWS event in scope."""
    mock_request.scope = {"root_path": ""}
    mock_request.app = sample_app
    return mock_request


class TestAWSAPIGatewayMiddleware:
    """Test cases for AWS API Gateway middleware with fixture-based mocking."""

    def test_middleware_initialization(
        self,
        mock_aws_api_gateway_middleware_common,
        aws_api_gateway_middleware_classes,
        sample_app
    ):
        """Test middleware initialization."""
        middleware = aws_api_gateway_middleware_classes['AWSAPIGatewayMiddleware'](sample_app)
        assert middleware.app == sample_app

    def test_dispatch_with_existing_root_path(
        self,
        mock_aws_api_gateway_middleware_common,
        middleware_instance,
        sample_request_with_existing_root_path,
        mock_call_next
    ):
        """Test dispatch when root_path is already set."""
        result = asyncio.run(middleware_instance.dispatch(sample_request_with_existing_root_path, mock_call_next))
        
        assert result == mock_call_next.return_value
        mock_call_next.assert_called_once_with(sample_request_with_existing_root_path)

    def test_dispatch_with_aws_event_default_stage(
        self,
        mock_aws_api_gateway_middleware_common,
        middleware_instance,
        sample_request_with_aws_event_default_stage,
        mock_call_next
    ):
        """Test dispatch with AWS event and default stage."""
        result = asyncio.run(middleware_instance.dispatch(sample_request_with_aws_event_default_stage, mock_call_next))
        
        assert result is not None
        mock_call_next.assert_called_once_with(sample_request_with_aws_event_default_stage)

    def test_dispatch_with_aws_event_custom_stage(
        self,
        mock_aws_api_gateway_middleware_common,
        middleware_instance,
        sample_request_with_aws_event_custom_stage,
        mock_call_next
    ):
        """Test dispatch with AWS event and custom stage."""
        result = asyncio.run(middleware_instance.dispatch(sample_request_with_aws_event_custom_stage, mock_call_next))
        
        assert result is not None
        mock_call_next.assert_called_once_with(sample_request_with_aws_event_custom_stage)
        assert middleware_instance.app.root_path == "/dev"
        assert sample_request_with_aws_event_custom_stage.scope["root_path"] == "/dev"

    def test_dispatch_with_docs_path(
        self,
        mock_aws_api_gateway_middleware_common,
        middleware_instance,
        sample_request_with_docs_path,
        mock_call_next
    ):
        """Test dispatch with /docs path."""
        result = asyncio.run(middleware_instance.dispatch(sample_request_with_docs_path, mock_call_next))
        
        assert result is not None
        mock_call_next.assert_called_once_with(sample_request_with_docs_path)

    def test_dispatch_with_stage_path_starting_with_stage(
        self,
        mock_aws_api_gateway_middleware_common,
        middleware_instance,
        sample_request_with_stage_path,
        mock_call_next
    ):
        """Test dispatch when request path starts with stage path."""
        result = asyncio.run(middleware_instance.dispatch(sample_request_with_stage_path, mock_call_next))
        
        assert result is not None
        mock_call_next.assert_called_once_with(sample_request_with_stage_path)
        assert sample_request_with_stage_path.app.openapi_url == "/dev/openapi.json"

    def test_dispatch_without_aws_event(
        self,
        mock_aws_api_gateway_middleware_common,
        middleware_instance,
        sample_request_without_aws_event,
        mock_call_next
    ):
        """Test dispatch without AWS event in scope."""
        result = asyncio.run(middleware_instance.dispatch(sample_request_without_aws_event, mock_call_next))
        
        assert result is not None
        mock_call_next.assert_called_once_with(sample_request_without_aws_event)


class TestMiddlewareConfiguration:
    """Test cases for middleware configuration with fixture-based mocking."""

    def test_middleware_with_multiple_apps(
        self,
        mock_aws_api_gateway_middleware_common,
        aws_api_gateway_middleware_classes
    ):
        """Test middleware with multiple FastAPI applications."""
        app1 = aws_api_gateway_middleware_classes['FastAPI']()
        app2 = aws_api_gateway_middleware_classes['FastAPI']()
        
        middleware1 = aws_api_gateway_middleware_classes['AWSAPIGatewayMiddleware'](app1)
        middleware2 = aws_api_gateway_middleware_classes['AWSAPIGatewayMiddleware'](app2)
        
        assert middleware1.app == app1
        assert middleware2.app == app2
        assert middleware1.app != middleware2.app

    def test_middleware_app_modification(
        self,
        mock_aws_api_gateway_middleware_common,
        middleware_instance,
        sample_app
    ):
        """Test that middleware properly modifies app properties."""
        # Create a request that will trigger app modification
        request = Mock()
        request.scope = {
            "root_path": "",
            "aws.event": {
                "pathParameters": {"proxy": "test"},
                "requestContext": {"stage": "production", "path": "/production/api/v1"},
                "path": "/api/v1",
            },
        }
        request.app = sample_app
        
        call_next = AsyncMock()
        call_next.return_value = Mock()
        
        result = asyncio.run(middleware_instance.dispatch(request, call_next))
        
        assert result is not None
        # Verify that the app properties were modified
        assert middleware_instance.app.root_path == "/production"
        assert request.scope["root_path"] == "/production"


class TestMiddlewareEdgeCases:
    """Test cases for middleware edge cases with fixture-based mocking."""

    def test_dispatch_with_empty_scope_raises_keyerror(
        self,
        mock_aws_api_gateway_middleware_common,
        middleware_instance,
        mock_call_next
    ):
        """Test dispatch with empty scope raises KeyError."""
        request = Mock()
        request.scope = {}
        request.app = Mock()
        
        with pytest.raises(KeyError, match="root_path"):
            asyncio.run(middleware_instance.dispatch(request, mock_call_next))

    def test_dispatch_with_malformed_aws_event_raises_keyerror(
        self,
        mock_aws_api_gateway_middleware_common,
        middleware_instance,
        mock_call_next
    ):
        """Test dispatch with malformed AWS event raises KeyError."""
        request = Mock()
        request.scope = {
            "root_path": "",
            "aws.event": {
                "pathParameters": None,
                "requestContext": {},
            },
        }
        request.app = Mock()
        
        with pytest.raises(KeyError, match="stage"):
            asyncio.run(middleware_instance.dispatch(request, mock_call_next))

    def test_dispatch_with_missing_request_context_raises_keyerror(
        self,
        mock_aws_api_gateway_middleware_common,
        middleware_instance,
        mock_call_next
    ):
        """Test dispatch with missing requestContext raises KeyError."""
        request = Mock()
        request.scope = {
            "root_path": "",
            "aws.event": {
                "pathParameters": {"proxy": "test"},
            },
        }
        request.app = Mock()
        
        with pytest.raises(KeyError, match="requestContext"):
            asyncio.run(middleware_instance.dispatch(request, mock_call_next))

    def test_dispatch_with_none_stage_raises_keyerror(
        self,
        mock_aws_api_gateway_middleware_common,
        middleware_instance,
        mock_call_next
    ):
        """Test dispatch with None stage raises KeyError when path is missing."""
        request = Mock()
        request.scope = {
            "root_path": "",
            "aws.event": {
                "pathParameters": {"proxy": "test"},
                "requestContext": {"stage": None, "path": "/test"},
            },
        }
        request.app = Mock()
        
        with pytest.raises(KeyError, match="path"):
            asyncio.run(middleware_instance.dispatch(request, mock_call_next))

    def test_dispatch_with_empty_stage_raises_keyerror(
        self,
        mock_aws_api_gateway_middleware_common,
        middleware_instance,
        mock_call_next
    ):
        """Test dispatch with empty stage raises KeyError when path is missing."""
        request = Mock()
        request.scope = {
            "root_path": "",
            "aws.event": {
                "pathParameters": {"proxy": "test"},
                "requestContext": {"stage": "", "path": "/test"},
            },
        }
        request.app = Mock()
        
        with pytest.raises(KeyError, match="path"):
            asyncio.run(middleware_instance.dispatch(request, mock_call_next))

    def test_dispatch_with_proper_empty_stage_handling(
        self,
        mock_aws_api_gateway_middleware_common,
        middleware_instance,
        mock_call_next
    ):
        """Test dispatch with empty stage but proper path handling."""
        request = Mock()
        request.scope = {
            "root_path": "",
            "aws.event": {
                "pathParameters": {"proxy": "test"},
                "requestContext": {"stage": "", "path": "/test"},
                "path": "/api"
            },
        }
        request.app = Mock()
        
        result = asyncio.run(middleware_instance.dispatch(request, mock_call_next))
        
        assert result is not None
        mock_call_next.assert_called_once_with(request)


class TestAsyncMiddlewareOperations:
    """Test cases for async middleware operations with fixture-based mocking."""

    def test_async_call_next_exception(
        self,
        mock_aws_api_gateway_middleware_common,
        middleware_instance,
        sample_request_with_existing_root_path
    ):
        """Test handling of exceptions in async call_next."""
        call_next = AsyncMock()
        call_next.side_effect = Exception("Async error")
        
        with pytest.raises(Exception, match="Async error"):
            asyncio.run(middleware_instance.dispatch(sample_request_with_existing_root_path, call_next))

    def test_async_middleware_execution_order(
        self,
        mock_aws_api_gateway_middleware_common,
        middleware_instance,
        sample_request_with_aws_event_custom_stage
    ):
        """Test that middleware executes in correct order."""
        call_next = AsyncMock()
        response = Mock()
        call_next.return_value = response
        
        # Track execution order
        execution_order = []
        
        async def track_call_next(request):
            execution_order.append("call_next_start")
            result = await call_next(request)
            execution_order.append("call_next_end")
            return result
        
        # Replace the call_next with our tracking version
        result = asyncio.run(middleware_instance.dispatch(sample_request_with_aws_event_custom_stage, track_call_next))
        
        assert result == response
        assert execution_order == ["call_next_start", "call_next_end"]
