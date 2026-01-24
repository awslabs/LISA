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

"""Tests for model registry."""
import sys
from pathlib import Path

import pytest

# Add the REST API source to the path
rest_api_src = Path(__file__).parent.parent.parent / "lib" / "serve" / "rest-api" / "src"
sys.path.insert(0, str(rest_api_src))

# Import the registry module directly to avoid lisa_serve package imports
registry_path = rest_api_src / "lisa_serve" / "registry"
sys.path.insert(0, str(registry_path))

from index import ModelRegistry  # noqa: E402


class TestModelRegistry:
    """Tests for ModelRegistry class."""

    def test_register_and_get_assets(self):
        """Test registering and retrieving model assets."""
        from unittest.mock import MagicMock

        registry = ModelRegistry()
        mock_adapter = MagicMock()
        mock_validator = MagicMock()

        registry.register(provider="test-provider", adapter=mock_adapter, validator=mock_validator)

        assets = registry.get_assets("test-provider")

        assert assets["adapter"] == mock_adapter
        assert assets["validator"] == mock_validator

    def test_register_multiple_providers(self):
        """Test registering multiple providers."""
        from unittest.mock import MagicMock

        registry = ModelRegistry()

        registry.register(provider="provider1", adapter=MagicMock(), validator=MagicMock())
        registry.register(provider="provider2", adapter=MagicMock(), validator=MagicMock())

        assert "provider1" in registry.registry
        assert "provider2" in registry.registry

    def test_get_assets_not_found(self):
        """Test getting assets for non-existent provider."""
        registry = ModelRegistry()

        with pytest.raises(KeyError) as exc_info:
            registry.get_assets("nonexistent-provider")

        assert "Model provider 'nonexistent-provider' not found" in str(exc_info.value)
        assert "Available providers:" in str(exc_info.value)

    def test_get_assets_shows_available_providers(self):
        """Test that error message shows available providers."""
        from unittest.mock import MagicMock

        registry = ModelRegistry()
        registry.register(provider="provider1", adapter=MagicMock(), validator=MagicMock())
        registry.register(provider="provider2", adapter=MagicMock(), validator=MagicMock())

        with pytest.raises(KeyError) as exc_info:
            registry.get_assets("nonexistent")

        error_msg = str(exc_info.value)
        assert "provider1" in error_msg
        assert "provider2" in error_msg

    def test_register_overwrites_existing(self):
        """Test that registering same provider overwrites previous registration."""
        from unittest.mock import MagicMock

        registry = ModelRegistry()
        adapter1 = MagicMock()
        adapter2 = MagicMock()

        registry.register(provider="test", adapter=adapter1, validator=MagicMock())
        registry.register(provider="test", adapter=adapter2, validator=MagicMock())

        assets = registry.get_assets("test")
        assert assets["adapter"] == adapter2
        assert assets["adapter"] != adapter1

    def test_registry_initialization(self):
        """Test that registry initializes with empty dict."""
        registry = ModelRegistry()

        assert isinstance(registry.registry, dict)
        assert len(registry.registry) == 0
