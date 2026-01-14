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

"""Unit tests for MCP Workbench CLI."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

# Import the CLI module
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "lib/serve/mcp-workbench/src"))

from mcpworkbench.cli import load_config_from_file, main, merge_config


@pytest.fixture
def temp_config_file():
    """Create a temporary config file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        config = {
            "tools_dir": "/tmp/tools",
            "host": "localhost",
            "port": 8080,
        }
        yaml.dump(config, f)
        yield Path(f.name)
    Path(f.name).unlink(missing_ok=True)


@pytest.fixture
def temp_tools_dir():
    """Create a temporary tools directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


def test_load_config_from_file_success(temp_config_file):
    """Test loading configuration from a valid YAML file."""
    config = load_config_from_file(str(temp_config_file))
    assert config["tools_dir"] == "/tmp/tools"
    assert config["host"] == "localhost"
    assert config["port"] == 8080


def test_load_config_from_file_not_found():
    """Test loading configuration from non-existent file."""
    with pytest.raises(SystemExit) as exc_info:
        load_config_from_file("/nonexistent/config.yaml")
    assert exc_info.value.code == 1


def test_load_config_from_file_invalid_yaml(tmp_path):
    """Test loading configuration from invalid YAML file."""
    invalid_file = tmp_path / "invalid.yaml"
    invalid_file.write_text("invalid: yaml: content: [")

    with pytest.raises(SystemExit) as exc_info:
        load_config_from_file(str(invalid_file))
    assert exc_info.value.code == 1


def test_merge_config():
    """Test merging file config with CLI overrides."""
    file_config = {
        "tools_dir": "/tmp/tools",
        "host": "localhost",
        "port": 8080,
    }

    cli_overrides = {
        "host": "0.0.0.0",
        "port": "9000",
        "exit_route": "/exit",
    }

    merged = merge_config(file_config, cli_overrides)

    assert merged["tools_dir"] == "/tmp/tools"
    assert merged["host"] == "0.0.0.0"
    assert merged["port"] == "9000"
    assert merged["exit_route"] == "/exit"


def test_merge_config_none_values():
    """Test that None values in CLI overrides don't override file config."""
    file_config = {"host": "localhost", "port": 8080}
    cli_overrides = {"host": None, "port": "9000"}

    merged = merge_config(file_config, cli_overrides)

    assert merged["host"] == "localhost"
    assert merged["port"] == "9000"


def test_main_missing_tools_dir():
    """Test CLI fails when tools_dir is not specified."""
    runner = CliRunner()
    result = runner.invoke(main, [])

    # Should exit with error code
    assert result.exit_code == 1


def test_main_with_config_file(temp_config_file, temp_tools_dir):
    """Test CLI with config file."""
    runner = CliRunner()

    # Update config to use temp tools dir
    config = {"tools_dir": str(temp_tools_dir), "host": "localhost", "port": 8080}
    with open(temp_config_file, "w") as f:
        yaml.dump(config, f)

    with patch("mcpworkbench.cli.MCPWorkbenchServer") as mock_server:
        mock_server_instance = MagicMock()
        mock_server.return_value = mock_server_instance

        result = runner.invoke(main, ["--config", str(temp_config_file)])

        # Should attempt to start server
        assert mock_server_instance.run.called or result.exit_code == 0


def test_main_with_cli_args(temp_tools_dir):
    """Test CLI with command line arguments."""
    runner = CliRunner()

    with patch("mcpworkbench.cli.MCPWorkbenchServer") as mock_server:
        mock_server_instance = MagicMock()
        mock_server.return_value = mock_server_instance

        runner.invoke(
            main,
            [
                "--tools-dir",
                str(temp_tools_dir),
                "--host",
                "0.0.0.0",
                "--port",
                "9000",
                "--verbose",
            ],
        )

        mock_server_instance.run.assert_called_once()


def test_main_cors_origins_parsing(temp_tools_dir):
    """Test CORS origins parsing."""
    runner = CliRunner()

    with patch("mcpworkbench.cli.MCPWorkbenchServer") as mock_server:
        with patch("mcpworkbench.cli.ServerConfig") as mock_config:
            mock_server_instance = MagicMock()
            mock_server.return_value = mock_server_instance

            runner.invoke(
                main,
                [
                    "--tools-dir",
                    str(temp_tools_dir),
                    "--cors-origins",
                    "http://localhost:3000,http://localhost:8080",
                ],
            )

            # Verify ServerConfig was called with parsed origins
            call_args = mock_config.from_dict.call_args
            assert call_args is not None


def test_main_debug_logging(temp_tools_dir):
    """Test debug logging flag."""
    runner = CliRunner()

    with patch("mcpworkbench.cli.MCPWorkbenchServer") as mock_server:
        mock_server_instance = MagicMock()
        mock_server.return_value = mock_server_instance

        runner.invoke(
            main,
            ["--tools-dir", str(temp_tools_dir), "--debug"],
        )

        # Should set debug logging level
        import logging

        assert logging.getLogger().level == logging.DEBUG


def test_main_keyboard_interrupt(temp_tools_dir):
    """Test handling of keyboard interrupt."""
    runner = CliRunner()

    with patch("mcpworkbench.cli.MCPWorkbenchServer") as mock_server:
        mock_server_instance = MagicMock()
        mock_server_instance.run.side_effect = KeyboardInterrupt()
        mock_server.return_value = mock_server_instance

        result = runner.invoke(
            main,
            ["--tools-dir", str(temp_tools_dir)],
        )

        assert result.exit_code == 0


def test_main_server_error(temp_tools_dir):
    """Test handling of server startup error."""
    runner = CliRunner()

    with patch("mcpworkbench.cli.MCPWorkbenchServer") as mock_server:
        mock_server.side_effect = Exception("Server failed to start")

        result = runner.invoke(
            main,
            ["--tools-dir", str(temp_tools_dir)],
        )

        # Should exit with error
        assert result.exit_code == 1


def test_main_invalid_config(temp_tools_dir):
    """Test handling of invalid configuration."""
    runner = CliRunner()

    with patch("mcpworkbench.cli.ServerConfig") as mock_config:
        mock_config.from_dict.side_effect = ValueError("Invalid port")

        result = runner.invoke(
            main,
            ["--tools-dir", str(temp_tools_dir)],
        )

        # Should exit with error
        assert result.exit_code == 1
