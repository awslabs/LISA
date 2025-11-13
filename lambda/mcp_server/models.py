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
from datetime import datetime
from enum import StrEnum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator
from typing_extensions import Self
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
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))

    # Timestamp of when the mcp server was created
    created: Optional[str] = Field(default_factory=lambda: datetime.now().isoformat())

    # Owner of the MCP user
    owner: str

    # URL of the MCP server
    url: str

    # Name of the MCP server
    name: str

    # Description of the MCP server
    description: Optional[str] = Field(default_factory=lambda: None)

    # Custom headers for the MCP client
    customHeaders: Optional[dict] = Field(default_factory=lambda: None)

    # Custom client properties for the MCP client
    clientConfig: Optional[dict] = Field(default_factory=lambda: None)

    # Status of the server set by admins
    status: Optional[HostedMcpServerStatus] = Field(default=HostedMcpServerStatus.STOPPED)

    # Groups of the MCP server
    groups: Optional[List[str]] = Field(default_factory=lambda: None)


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

    command: Union[str, List[str]]
    interval: int = Field(gt=0)
    startPeriod: int = Field(ge=0)
    timeout: int = Field(gt=0)
    retries: int = Field(gt=0)


class AutoScalingConfig(BaseModel):
    """Auto-scaling configuration for hosted MCP servers."""

    minCapacity: int
    maxCapacity: int
    targetValue: Optional[int] = Field(default=None)
    metricName: Optional[str] = Field(default=None)
    duration: Optional[int] = Field(default=None)
    cooldown: Optional[int] = Field(default=None)


class AutoScalingConfigUpdate(BaseModel):
    """Updatable auto-scaling configuration for hosted MCP servers (all fields optional)."""

    minCapacity: Optional[int] = Field(default=None)
    maxCapacity: Optional[int] = Field(default=None)
    targetValue: Optional[int] = Field(default=None)
    metricName: Optional[str] = Field(default=None)
    duration: Optional[int] = Field(default=None)
    cooldown: Optional[int] = Field(default=None)


class HostedMcpServerModel(BaseModel):
    """
    A Pydantic model representing a hosted MCP server configuration.
    This model is used for creating MCP servers that are deployed on ECS Fargate.
    """

    # Unique identifier for the mcp server
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))

    # Timestamp of when the mcp server was created
    created: Optional[str] = Field(default_factory=lambda: datetime.now().isoformat())

    # Owner of the MCP server
    owner: str

    # Name of the MCP server
    name: str

    # Description of the MCP server
    description: Optional[str] = Field(default_factory=lambda: None)

    # Command to start the server
    startCommand: str

    # Port number (optional, used for HTTP/SSE servers)
    port: Optional[int] = Field(default=None)

    # Server type: 'stdio', 'http', or 'sse'
    serverType: str

    # Container image (optional)
    # If provided without s3Path: use as pre-built container image
    # If provided with s3Path: use as base image for building from S3 artifacts
    image: Optional[str] = Field(default=None)

    # S3 path to server artifacts (binaries, Python files, etc.)
    # If provided with image: image is used as base image for building
    # If provided without image: default base image is used
    s3Path: Optional[str] = Field(default=None)

    # Auto-scaling configuration
    autoScalingConfig: AutoScalingConfig

    # Load balancer configuration (optional, will use defaults if not provided)
    loadBalancerConfig: Optional[LoadBalancerConfig] = Field(default=None)

    # Container health check configuration (optional, will use defaults if not provided)
    containerHealthCheckConfig: Optional[ContainerHealthCheckConfig] = Field(default=None)

    # Environment variables for the container
    environment: Optional[Dict[str, str]] = Field(default_factory=lambda: None)

    # IAM role ARN for task execution (optional, will be auto-created if not provided)
    taskExecutionRoleArn: Optional[str] = Field(default=None)

    # IAM role ARN for running tasks (optional, will be auto-created if not provided)
    taskRoleArn: Optional[str] = Field(default=None)

    # Fargate CPU units (defaults to 256 which equals 0.25 vCPU)
    cpu: Optional[int] = Field(default=256)

    # Fargate memory limit in MiB (defaults to 512 MiB)
    memoryLimitMiB: Optional[int] = Field(default=512)

    # Groups of the MCP server (for authorization)
    groups: Optional[List[str]] = Field(default_factory=lambda: None)

    # Status of the server
    status: Optional[HostedMcpServerStatus] = Field(default=HostedMcpServerStatus.CREATING)


class UpdateHostedMcpServerRequest(BaseModel):
    """Specifies parameters for hosted MCP server update requests."""

    enabled: Optional[bool] = None
    autoScalingConfig: Optional[AutoScalingConfigUpdate] = None
    environment: Optional[Dict[str, str]] = None
    containerHealthCheckConfig: Optional[ContainerHealthCheckConfig] = None
    loadBalancerConfig: Optional[LoadBalancerConfig] = None
    cpu: Optional[int] = None
    memoryLimitMiB: Optional[int] = None
    description: Optional[str] = None
    groups: Optional[List[str]] = None

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
    def validate_autoscaling_config(cls, config: Optional[AutoScalingConfig]) -> Optional[AutoScalingConfig]:
        """Validates auto-scaling configuration."""
        if config is not None and not config:
            raise ValueError("The autoScalingConfig must not be null if defined in request payload.")
        return config

    @field_validator("containerHealthCheckConfig")
    @classmethod
    def validate_container_health_check_config(
        cls, config: Optional[ContainerHealthCheckConfig]
    ) -> Optional[ContainerHealthCheckConfig]:
        """Validates container health check configuration."""
        if config is not None and not config:
            raise ValueError("The containerHealthCheckConfig must not be null if defined in request payload.")
        return config

    @field_validator("loadBalancerConfig")
    @classmethod
    def validate_load_balancer_config(cls, config: Optional[LoadBalancerConfig]) -> Optional[LoadBalancerConfig]:
        """Validates load balancer configuration."""
        if config is not None and not config:
            raise ValueError("The loadBalancerConfig must not be null if defined in request payload.")
        return config

    @field_validator("cpu")
    @classmethod
    def validate_cpu(cls, cpu: Optional[int]) -> Optional[int]:
        """Validates CPU units."""
        if cpu is not None:
            # Fargate CPU must be in valid units: 256, 512, 1024, 2048, 4096
            valid_cpu_values = [256, 512, 1024, 2048, 4096]
            if cpu not in valid_cpu_values:
                raise ValueError(f"CPU must be one of {valid_cpu_values}")
        return cpu

    @field_validator("memoryLimitMiB")
    @classmethod
    def validate_memory(cls, memory: Optional[int]) -> Optional[int]:
        """Validates memory limit."""
        if memory is not None:
            if memory < 512:
                raise ValueError("Memory limit must be at least 512 MiB")
            if memory > 30720:
                raise ValueError("Memory limit must be at most 30720 MiB")
        return memory
