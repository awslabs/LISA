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

"""Unit tests for MCP Workbench middleware."""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

# Import the middleware module
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib/serve/mcp-workbench/src"))

from mcpworkbench.config.models import CORSConfig
from mcpworkbench.server.middleware import CORSMiddleware, ExitRouteMiddleware, RescanMiddleware


@pytest.fixture
def mock_app():
    """Create a mock ASGI app."""
    return Mock()


@pytest.fixture
def mock_request():
    """Create a mock request."""
    request = Mock()
    request.url = Mock()
    request.url.path = "/test"
    return request


@pytest.fixture
def mock_call_next():
    """Create a mock call_next function."""

    async def call_next(request):
        return Mock(status_code=200)

    return call_next


@pytest.fixture
def cors_config():
    """Create a CORS configuration."""
    return CORSConfig(
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
        expose_headers=[],
        max_age=600,
    )


def test_cors_middleware_init(mock_app, cors_config):
    """Test CORSMiddleware initialization."""
    middleware = CORSMiddleware(mock_app, cors_config)
    assert middleware is not None


@pytest.mark.asyncio
async def test_exit_route_middleware_exit_path(mock_app, mock_request):
    """Test ExitRouteMiddleware handles exit path."""
    middleware = ExitRouteMiddleware(mock_app, "/exit")
    mock_request.url.path = "/exit"

    with patch.object(middleware, "_delayed_exit", new_callable=AsyncMock):
        response = await middleware.dispatch(mock_request, AsyncMock())

        assert response.status_code == 200
        body = response.body.decode()
        assert "shutting down" in body.lower()


@pytest.mark.asyncio
async def test_exit_route_middleware_normal_path(mock_app, mock_request, mock_call_next):
    """Test ExitRouteMiddleware passes through normal requests."""
    middleware = ExitRouteMiddleware(mock_app, "/exit")
    mock_request.url.path = "/other"

    response = await middleware.dispatch(mock_request, mock_call_next)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_exit_route_middleware_trailing_slash(mock_app, mock_request):
    """Test ExitRouteMiddleware handles trailing slashes."""
    middleware = ExitRouteMiddleware(mock_app, "/exit/")
    mock_request.url.path = "/exit"

    with patch.object(middleware, "_delayed_exit", new_callable=AsyncMock):
        response = await middleware.dispatch(mock_request, AsyncMock())

        assert response.status_code == 200


@pytest.mark.asyncio
async def test_rescan_middleware_rescan_path(mock_app, mock_request):
    """Test RescanMiddleware handles rescan path."""
    mock_tool_discovery = Mock()
    mock_tool_registry = Mock()

    # Create mock rescan result
    mock_rescan_result = Mock()
    mock_rescan_result.tools_added = ["tool1"]
    mock_rescan_result.tools_updated = ["tool2"]
    mock_rescan_result.tools_removed = []
    mock_rescan_result.total_tools = 2
    mock_rescan_result.errors = []

    mock_tool_discovery.rescan_tools.return_value = mock_rescan_result
    mock_tool_discovery.discover_tools.return_value = []

    middleware = RescanMiddleware(mock_app, "/rescan", mock_tool_discovery, mock_tool_registry)
    mock_request.url.path = "/rescan"

    response = await middleware.dispatch(mock_request, AsyncMock())

    assert response.status_code == 200
    body = response.body.decode()
    assert "success" in body


@pytest.mark.asyncio
async def test_rescan_middleware_normal_path(mock_app, mock_request, mock_call_next):
    """Test RescanMiddleware passes through normal requests."""
    mock_tool_discovery = Mock()
    mock_tool_registry = Mock()

    middleware = RescanMiddleware(mock_app, "/rescan", mock_tool_discovery, mock_tool_registry)
    mock_request.url.path = "/other"

    response = await middleware.dispatch(mock_request, mock_call_next)

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_rescan_middleware_error(mock_app, mock_request):
    """Test RescanMiddleware handles errors during rescan."""
    mock_tool_discovery = Mock()
    mock_tool_registry = Mock()

    mock_tool_discovery.rescan_tools.side_effect = Exception("Rescan failed")

    middleware = RescanMiddleware(mock_app, "/rescan", mock_tool_discovery, mock_tool_registry)
    mock_request.url.path = "/rescan"

    response = await middleware.dispatch(mock_request, AsyncMock())

    assert response.status_code == 500
    body = response.body.decode()
    assert "error" in body.lower()


@pytest.mark.asyncio
async def test_rescan_middleware_updates_registry(mock_app, mock_request):
    """Test RescanMiddleware updates tool registry after rescan."""
    mock_tool_discovery = Mock()
    mock_tool_registry = Mock()

    mock_rescan_result = Mock()
    mock_rescan_result.tools_added = []
    mock_rescan_result.tools_updated = []
    mock_rescan_result.tools_removed = []
    mock_rescan_result.total_tools = 0
    mock_rescan_result.errors = []

    mock_tool_discovery.rescan_tools.return_value = mock_rescan_result
    mock_tool_discovery.discover_tools.return_value = []

    middleware = RescanMiddleware(mock_app, "/rescan", mock_tool_discovery, mock_tool_registry)
    mock_request.url.path = "/rescan"

    await middleware.dispatch(mock_request, AsyncMock())

    # Verify registry was updated
    mock_tool_registry.update_registry.assert_called_once()
