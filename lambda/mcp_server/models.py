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

import uuid
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, field_validator, model_validator
from utilities.time import iso_string
from utilities.validation import validate_any_fields_defined


class HostedMcpServerStatus(StrEnum):
    """Defines possible MCP server deployment states."""

    CREATING = "Creating"
    IN_SERVICE = "InService"
    STARTING = "Starting"
    STOPPING = "Stopping"
    STOPPED = "Stopped"
    UPDATING = "Updating"
    DELETING = "Deleting"
    FAILED = "Failed"


class McpServerStatus(StrEnum):
    """Enum representing the prompt template type."""

    ACTIVE = "active"
    INACTIVE = "inactive"


class McpServerModel(BaseModel):
    """
    A Pydantic model representing a template for prompts.
    Contains metadata and functionality to create new revisions.
    """

    # Unique identifier for the mcp server
    id: str | None = Field(default_factory=lambda: str(uuid.uuid4()))

    # Timestamp of when the mcp server was created
    created: str | None = Field(default_factory=iso_string)

    # Owner of the MCP user
    owner: str

    # URL of the MCP server
    url: str

    # Name of the MCP server
    name: str

    # Description of the MCP server
    description: str | None = Field(default_factory=lambda: None)

    # Custom headers for the MCP client
    customHeaders: dict | None = Field(default_factory=lambda: None)

    # Custom client properties for the MCP client
    clientConfig: dict | None = Field(default_factory=lambda: None)

    # Status of the server set by admins
    status: McpServerStatus | None = Field(default=McpServerStatus.ACTIVE)

    # Groups of the MCP server
    groups: list[str] | None = Field(default_factory=lambda: None)


class LoadBalancerHealthCheckConfig(BaseModel):
    """Specifies health check parameters for load balancer configuration."""

    path: str = Field(min_length=1)
    interval: int = Field(gt=0)
    timeout: int = Field(gt=0)
    healthyThresholdCount: int = Field(gt=0)
    unhealthyThresholdCount: int = Field(gt=0)


class LoadBalancerConfig(BaseModel):
    """Defines load balancer settings."""

    healthCheckConfig: LoadBalancerHealthCheckConfig


class ContainerHealthCheckConfig(BaseModel):
    """Specifies container health check parameters."""

    command: str | list[str]
    interval: int = Field(gt=0)
    startPeriod: int = Field(ge=0)
    timeout: int = Field(gt=0)
    retries: int = Field(gt=0)


class AutoScalingConfig(BaseModel):
    """Auto-scaling configuration for hosted MCP servers."""

    minCapacity: int
    maxCapacity: int
    targetValue: int | None = Field(default=None)
    metricName: str | None = Field(default=None)
    duration: int | None = Field(default=None)
    cooldown: int | None = Field(default=None)


class AutoScalingConfigUpdate(BaseModel):
    """Updatable auto-scaling configuration for hosted MCP servers (all fields optional)."""

    minCapacity: int | None = Field(default=None)
    maxCapacity: int | None = Field(default=None)
    targetValue: int | None = Field(default=None)
    metricName: str | None = Field(default=None)
    duration: int | None = Field(default=None)
    cooldown: int | None = Field(default=None)


class HostedMcpServerModel(BaseModel):
    """
    A Pydantic model representing a hosted MCP server configuration.
    This model is used for creating MCP servers that are deployed on ECS Fargate.
    """

    # Unique identifier for the mcp server
    id: str | None = Field(default_factory=lambda: str(uuid.uuid4()))

    # Timestamp of when the mcp server was created
    created: str | None = Field(default_factory=iso_string)

    # Owner of the MCP server
    owner: str

    # Name of the MCP server
    name: str

    # Description of the MCP server
    description: str | None = Field(default_factory=lambda: None)

    # Command to start the server
    startCommand: str

    # Port number (optional, used for HTTP/SSE servers)
    port: int | None = Field(default=None)

    # Server type: 'stdio', 'http', or 'sse'
    serverType: str

    # Container image (optional)
    # If provided without s3Path: use as pre-built container image
    # If provided with s3Path: use as base image for building from S3 artifacts
    image: str | None = Field(default=None)

    # S3 path to server artifacts (binaries, Python files, etc.)
    # If provided with image: image is used as base image for building
    # If provided without image: default base image is used
    s3Path: str | None = Field(default=None)

    # Auto-scaling configuration
    autoScalingConfig: AutoScalingConfig

    # Load balancer configuration (optional, will use defaults if not provided)
    loadBalancerConfig: LoadBalancerConfig | None = Field(default=None)

    # Container health check configuration (optional, will use defaults if not provided)
    containerHealthCheckConfig: ContainerHealthCheckConfig | None = Field(default=None)

    # Environment variables for the container
    environment: dict[str, str] | None = Field(default_factory=lambda: None)

    # IAM role ARN for task execution (optional, will be auto-created if not provided)
    taskExecutionRoleArn: str | None = Field(default=None)

    # IAM role ARN for running tasks (optional, will be auto-created if not provided)
    taskRoleArn: str | None = Field(default=None)

    # Fargate CPU units (defaults to 256 which equals 0.25 vCPU)
    cpu: int | None = Field(default=256)

    # Fargate memory limit in MiB (defaults to 512 MiB)
    memoryLimitMiB: int | None = Field(default=512)

    # Groups of the MCP server (for authorization)
    groups: list[str] | None = Field(default_factory=lambda: None)

    # Status of the server
    status: HostedMcpServerStatus | None = Field(default=HostedMcpServerStatus.CREATING)


class UpdateHostedMcpServerRequest(BaseModel):
    """Specifies parameters for hosted MCP server update requests."""

    enabled: bool | None = None
    autoScalingConfig: AutoScalingConfigUpdate | None = None
    environment: dict[str, str] | None = None
    containerHealthCheckConfig: ContainerHealthCheckConfig | None = None
    loadBalancerConfig: LoadBalancerConfig | None = None
    cpu: int | None = None
    memoryLimitMiB: int | None = None
    description: str | None = None
    groups: list[str] | None = None

    @model_validator(mode="after")
    def validate_update_request(self) -> Self:
        """Validates update request parameters."""
        fields = [
            self.enabled,
            self.autoScalingConfig,
            self.environment,
            self.containerHealthCheckConfig,
            self.loadBalancerConfig,
            self.cpu,
            self.memoryLimitMiB,
            self.description,
            self.groups,
        ]
        if not validate_any_fields_defined(fields):
            raise ValueError(
                "At least one field out of enabled, autoScalingConfig, environment, "
                "containerHealthCheckConfig, loadBalancerConfig, cpu, memoryLimitMiB, "
                "description, or groups must be defined in request payload."
            )
        return self

    @field_validator("autoScalingConfig")
    @classmethod
    def validate_autoscaling_config(cls, config: AutoScalingConfig | None) -> AutoScalingConfig | None:
        """Validates auto-scaling configuration."""
        if config is not None and not config:
            raise ValueError("The autoScalingConfig must not be null if defined in request payload.")
        return config

    @field_validator("containerHealthCheckConfig")
    @classmethod
    def validate_container_health_check_config(
        cls, config: ContainerHealthCheckConfig | None
    ) -> ContainerHealthCheckConfig | None:
        """Validates container health check configuration."""
        if config is not None and not config:
            raise ValueError("The containerHealthCheckConfig must not be null if defined in request payload.")
        return config

    @field_validator("loadBalancerConfig")
    @classmethod
    def validate_load_balancer_config(cls, config: LoadBalancerConfig | None) -> LoadBalancerConfig | None:
        """Validates load balancer configuration."""
        if config is not None and not config:
            raise ValueError("The loadBalancerConfig must not be null if defined in request payload.")
        return config

    @field_validator("cpu")
    @classmethod
    def validate_cpu(cls, cpu: int | None) -> int | None:
        """Validates CPU units."""
        if cpu is not None:
            # Fargate CPU must be in valid units: 256, 512, 1024, 2048, 4096
            valid_cpu_values = [256, 512, 1024, 2048, 4096]
            if cpu not in valid_cpu_values:
                raise ValueError(f"CPU must be one of {valid_cpu_values}")
        return cpu

    @field_validator("memoryLimitMiB")
    @classmethod
    def validate_memory(cls, memory: int | None) -> int | None:
        """Validates memory limit."""
        if memory is not None:
            if memory < 512:
                raise ValueError("Memory limit must be at least 512 MiB")
            if memory > 30720:
                raise ValueError("Memory limit must be at most 30720 MiB")
        return memory
