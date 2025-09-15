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

"""Integration tests for MCP Workbench server."""

import pytest

FASTMCP_AVAILABLE = True


pytestmark = pytest.mark.skipif(
    not FASTMCP_AVAILABLE, reason="FastMCP 2.0 not available - integration tests require FastMCP"
)


@pytest.mark.skipif(not FASTMCP_AVAILABLE, reason="FastMCP 2.0 required for integration tests")
def test_fastmcp_integration_placeholder():
    """Placeholder test for FastMCP 2.0 integration tests.

    Since we've migrated to pure FastMCP 2.0, these integration tests need to be
    rewritten to test MCP protocol directly rather than REST API endpoints.

    TODO: Implement proper FastMCP 2.0 integration tests that:
    1. Start the FastMCP server
    2. Connect via MCP client
    3. Test tool discovery and execution via MCP protocol
    4. Test management tools (rescan_tools, exit_server)
    """
    assert True  # Placeholder - tests pass but indicate work needed


# Note: The previous REST API integration tests have been removed as they are no longer
# applicable to the pure FastMCP 2.0 architecture. New integration tests should:
#
# 1. Use an MCP client to connect to the server
# 2. Test tool discovery via MCP protocol
# 3. Test tool execution via MCP protocol
# 4. Test management tools as native MCP tools
#
# This requires either:
# - A proper MCP client implementation
# - Or mocking the MCP protocol for testing
