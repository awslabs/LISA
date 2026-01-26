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

"""Configuration models for MCP Workbench."""


from pydantic import BaseModel, Field


class CORSConfig(BaseModel):
    """CORS configuration settings."""

    allow_origins: list[str] = Field(default=["*"], description="Allowed origins for CORS")
    allow_methods: list[str] = Field(default=["GET", "POST", "OPTIONS"], description="Allowed HTTP methods")
    allow_headers: list[str] = Field(default=["*"], description="Allowed headers")
    allow_credentials: bool = Field(default=True, description="Allow credentials in CORS requests")
    expose_headers: list[str] = Field(default=[], description="Headers to expose to the browser")
    max_age: int = Field(default=600, description="Maximum age for CORS preflight cache")


class ServerConfig(BaseModel):
    """Main server configuration."""

    # Server settings - using CLI-compatible names internally, but mapped from external names
    server_host: str = Field(default="127.0.0.1", description="Server host address")
    server_port: int = Field(default=8000, description="Server port")

    # Tool settings
    tools_directory: str = Field(..., description="Directory containing tool files")

    # Management tool settings
    exit_route_path: str | None = Field(default=None, description="Enable exit_server MCP tool when set")
    rescan_route_path: str | None = Field(default=None, description="Enable rescan_tools MCP tool when set")

    # CORS settings
    cors_settings: CORSConfig = Field(default_factory=CORSConfig, description="CORS configuration")

    @classmethod
    def from_dict(cls, data: dict) -> "ServerConfig":
        """Create ServerConfig from dictionary, handling both CLI and YAML formats."""
        # Create a copy to avoid modifying the original
        config_data = data.copy()

        # Map CLI/YAML names to internal property names
        field_mappings = {
            # Server settings
            "host": "server_host",
            "port": "server_port",
            # Tool settings
            "tools_dir": "tools_directory",
            # Route settings
            "mcp_route": "mcp_route_path",
            "exit_route": "exit_route_path",
            "rescan_route": "rescan_route_path",
        }

        # Apply field mappings
        for yaml_key, internal_key in field_mappings.items():
            if yaml_key in config_data:
                config_data[internal_key] = config_data.pop(yaml_key)

        # Handle CORS origins - support both simple list and full settings
        if "cors_origins" in config_data:
            cors_origins = config_data.pop("cors_origins")

            # If we don't have cors_settings yet, create one
            if "cors_settings" not in config_data:
                config_data["cors_settings"] = {}

            # If cors_settings is not a dict, make it one
            if not isinstance(config_data["cors_settings"], dict):
                config_data["cors_settings"] = {}

            # Set the origins
            config_data["cors_settings"]["allow_origins"] = cors_origins

        # Handle cors_settings
        if "cors_settings" in config_data and isinstance(config_data["cors_settings"], dict):
            config_data["cors_settings"] = CORSConfig(**config_data["cors_settings"])

        return cls(**config_data)
