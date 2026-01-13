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

"""Command Line Interface for MCP Workbench."""

import logging
import re
import sys
from pathlib import Path
from typing import Optional

import click
import yaml

from .config.models import ServerConfig
from .core.tool_discovery import ToolDiscovery
from .core.tool_registry import ToolRegistry
from .server.mcp_server import MCPWorkbenchServer

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def load_config_from_file(config_path: str) -> dict:
    """Load configuration from YAML file."""
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        logger.error(f"Error parsing configuration file: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error loading configuration file: {e}")
        sys.exit(1)


def merge_config(file_config: dict, cli_overrides: dict) -> dict:
    """Merge file configuration with CLI overrides."""
    merged = file_config.copy()

    # Apply CLI overrides
    for key, value in cli_overrides.items():
        if value is not None:
            merged[key] = value

    return merged


@click.command()
@click.option("--config", "-c", type=click.Path(exists=True, path_type=Path), help="Path to YAML configuration file")
@click.option(
    "--tools-dir",
    "-t",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Directory containing tool files",
)
@click.option("--host", default=None, help="Server host address (default: 127.0.0.1)")
@click.option("--port", "-p", type=int, default=None, help="Server port (default: 8000)")
@click.option("--exit-route", default=None, help="Enable exit_server MCP tool (optional)")
@click.option("--rescan-route", default=None, help="Enable rescan_tools MCP tool (optional)")
@click.option("--cors-origins", default=None, help="Comma-separated list of allowed CORS origins (default: *)")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--debug", is_flag=True, help="Enable debug logging")
def main(
    config: Optional[Path],
    tools_dir: Optional[Path],
    host: Optional[str],
    port: Optional[int],
    exit_route: Optional[str],
    rescan_route: Optional[str],
    cors_origins: Optional[str],
    verbose: bool,
    debug: bool,
) -> None:
    """MCP Workbench - A dynamic host for Python files used as MCP tools."""

    # Set logging level
    if debug:
        logging.getLogger().setLevel(logging.DEBUG)
    elif verbose:
        logging.getLogger().setLevel(logging.INFO)

    logger.info("Starting MCP Workbench...")

    # Load configuration
    file_config = {}
    if config:
        logger.info(f"Loading configuration from {config}")
        file_config = load_config_from_file(str(config))

    # Prepare CLI overrides
    cli_overrides = {}

    if tools_dir:
        cli_overrides["tools_dir"] = str(tools_dir)
    if host:
        cli_overrides["host"] = host
    if port:
        cli_overrides["port"] = str(port)
    if exit_route:
        cli_overrides["exit_route"] = exit_route
    if rescan_route:
        cli_overrides["rescan_route"] = rescan_route

    # Handle CORS origins
    if cors_origins:
        cleaned_origins = re.sub(r'^([\s"]+)?(.+?)([\s"]*)?$', r"\2", cors_origins)
        origins_list: list[str] = [origin.strip() for origin in cleaned_origins.split(",")]
        cli_overrides["cors_origins"] = ",".join(origins_list)

    # Merge configurations
    merged_config = merge_config(file_config, cli_overrides)

    # Validate required configuration
    if "tools_dir" not in merged_config:
        logger.error("Tools directory must be specified via --tools-dir or configuration file")
        sys.exit(1)

    # Create server configuration
    try:
        server_config = ServerConfig.from_dict(merged_config)
    except Exception as e:
        logger.error(f"Invalid configuration: {e}")
        sys.exit(1)

    logger.info("Configuration loaded:")
    logger.info(f"  Tools directory: {server_config.tools_directory}")
    logger.info(f"  Server: {server_config.server_host}:{server_config.server_port}")
    logger.info("  Protocol: Pure MCP via FastMCP 2.0")
    if server_config.exit_route_path:
        logger.info(f"  Exit tool enabled: {server_config.exit_route_path}")
    if server_config.rescan_route_path:
        logger.info(f"  Rescan tool enabled: {server_config.rescan_route_path}")

    # Initialize components
    try:
        tool_discovery = ToolDiscovery(server_config.tools_directory)
        tool_registry = ToolRegistry()

        # Create and start server
        server = MCPWorkbenchServer(server_config, tool_discovery, tool_registry)

        logger.info("Server initialized successfully")
        server.run()

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt - shutting down")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        if debug:
            import traceback  # noqa: PLC0415

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
