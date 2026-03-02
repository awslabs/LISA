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

"""Unit tests for ConfigMixin."""

import pytest
import responses
from lisapy import LisaApi


class TestConfigMixin:
    """Test suite for config-related operations."""

    @responses.activate
    def test_get_configs_global(self, lisa_api: LisaApi, api_url: str, mock_configs_response: list):
        """Test getting global configurations."""
        responses.add(responses.GET, f"{api_url}/configuration", json=mock_configs_response, status=200)

        configs = lisa_api.get_configs()

        assert len(configs) == 3
        assert configs[0]["parameter"] == "maxTokens"
        assert configs[1]["value"] == "0.7"
        # Verify default scope is global
        assert responses.calls[0].request.params["configScope"] == "global"

    @responses.activate
    def test_get_configs_custom_scope(self, lisa_api: LisaApi, api_url: str):
        """Test getting configurations with custom scope."""
        user_configs = [
            {"configScope": "user", "parameter": "theme", "value": "dark"},
            {"configScope": "user", "parameter": "language", "value": "en"},
        ]

        responses.add(responses.GET, f"{api_url}/configuration", json=user_configs, status=200)

        configs = lisa_api.get_configs(config_scope="user")

        assert len(configs) == 2
        assert configs[0]["configScope"] == "user"
        assert responses.calls[0].request.params["configScope"] == "user"

    @responses.activate
    def test_get_configs_empty(self, lisa_api: LisaApi, api_url: str):
        """Test getting configurations when none exist."""
        responses.add(responses.GET, f"{api_url}/configuration", json=[], status=200)

        configs = lisa_api.get_configs()

        assert len(configs) == 0

    @responses.activate
    def test_get_configs_error(self, lisa_api: LisaApi, api_url: str):
        """Test error handling when getting configs fails."""
        responses.add(responses.GET, f"{api_url}/configuration", json={"error": "Unauthorized"}, status=401)

        with pytest.raises(Exception):
            lisa_api.get_configs()
