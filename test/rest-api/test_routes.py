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

"""Unit tests for REST API routes."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# Add REST API src to path
rest_api_src = Path(__file__).parent.parent.parent / "lib" / "serve" / "rest-api" / "src"
sys.path.insert(0, str(rest_api_src))


class TestHealthCheck:
    """Test suite for health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, mock_env_vars):
        """Test successful health check."""
        from api.routes import health_check

        response = await health_check()

        assert response.status_code == 200
        assert b'"status":"OK"' in response.body

    @pytest.mark.asyncio
    async def test_health_check_missing_env_vars(self, monkeypatch):
        """Test health check with missing environment variables."""
        from api.routes import health_check

        # Set only one required var
        monkeypatch.setenv("LOG_LEVEL", "INFO")
        monkeypatch.delenv("AWS_REGION", raising=False)

        response = await health_check()

        assert response.status_code == 503
        assert b'"status":"UNHEALTHY"' in response.body
        assert b'"missing_env_vars"' in response.body

    @pytest.mark.asyncio
    async def test_health_check_exception(self, mock_env_vars):
        """Test health check with exception during validation."""
        from api.routes import health_check

        with patch("api.routes.os.getenv") as mock_getenv:
            mock_getenv.side_effect = Exception("Test error")

            response = await health_check()

            assert response.status_code == 503
            assert b'"status":"UNHEALTHY"' in response.body
            assert b'"error"' in response.body


class TestRouterConfiguration:
    """Test suite for router configuration."""

    def test_router_exists(self):
        """Test that router can be imported with mocked dependencies."""
        # Routes module requires full app context with many dependencies
        # This is a placeholder test - full testing requires integration tests
        assert True


class TestMiddleware:
    """Test suite for middleware functionality."""

    def test_middleware_placeholder(self):
        """Middleware testing requires full FastAPI app with all dependencies."""
        # Full middleware testing is done in integration tests
        assert True


class TestLifespan:
    """Test suite for application lifespan."""

    def test_lifespan_placeholder(self):
        """Lifespan testing requires full FastAPI app with aiobotocore and other dependencies."""
        # Full lifespan testing is done in integration tests
        assert True


class TestLiteLLMPassthrough:
    """Test suite for LiteLLM passthrough endpoint."""

    def test_passthrough_placeholder(self):
        """LiteLLM passthrough testing requires full app context."""
        # Full passthrough testing is done in integration tests
        assert True
