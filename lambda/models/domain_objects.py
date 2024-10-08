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

"""Domain objects for interacting with the model endpoints."""

from enum import Enum
from typing import Annotated, List, Optional, Union

from pydantic import BaseModel
from pydantic.functional_validators import AfterValidator, field_validator, model_validator
from typing_extensions import Self
from utilities.validators import validate_instance_type


class InferenceContainer(str, Enum):
    """Enum representing the interface container type."""

    def __str__(self) -> str:
        """Represent the enum as a string."""
        return str(self.value)

    TGI = "tgi"
    TEI = "tei"
    VLLM = "vllm"


class ModelStatus(str, Enum):
    """Enum representing a model status."""

    def __str__(self) -> str:
        """Represent the enum as a string."""
        return str(self.value)

    CREATING = "Creating"
    IN_SERVICE = "InService"
    STARTING = "Starting"
    STOPPING = "Stopping"
    STOPPED = "Stopped"
    UPDATING = "Updating"
    DELETING = "Deleting"
    FAILED = "Failed"


class ModelType(str, Enum):
    """Enum representing a model type."""

    def __str__(self) -> str:
        """Represent the enum as a string."""
        return str(self.value)

    TEXTGEN = "textgen"
    EMBEDDING = "embedding"


class MetricConfig(BaseModel):
    """Metric configuration for autoscaling."""

    albMetricName: str
    targetValue: int
    duration: int
    estimatedInstanceWarmup: int


class LoadBalancerHealthCheckConfig(BaseModel):
    """Health check configuration for a load balancer."""

    path: str
    interval: int
    timeout: int
    healthyThresholdCount: int
    unhealthyThresholdCount: int


class LoadBalancerConfig(BaseModel):
    """Load balancer configuration."""

    healthCheckConfig: LoadBalancerHealthCheckConfig


class AutoScalingConfig(BaseModel):
    """Autoscaling configuration upon model creation."""

    minCapacity: int
    maxCapacity: int
    cooldown: int
    defaultInstanceWarmup: int
    metricConfig: MetricConfig


class AutoScalingInstanceConfig(BaseModel):
    """Autoscaling instance count configuration upon model update."""

    minCapacity: Optional[int] = None
    maxCapacity: Optional[int] = None
    desiredCapacity: Optional[int] = None


class ContainerHealthCheckConfig(BaseModel):
    """Health check configuration for a container."""

    command: Union[str, list[str]]
    interval: int
    startPeriod: int
    timeout: int
    retries: int


class ContainerConfigImage(BaseModel):
    """Image image configuration for a container."""

    baseImage: str
    type: str


class ContainerConfig(BaseModel):
    """Container configuration."""

    image: ContainerConfigImage
    sharedMemorySize: int
    healthCheckConfig: ContainerHealthCheckConfig
    environment: dict[str, str]


class LISAModel(BaseModel):
    """Core model definition fields."""

    autoScalingConfig: Optional[AutoScalingConfig] = None
    containerConfig: Optional[ContainerConfig] = None
    inferenceContainer: Optional[InferenceContainer] = None
    instanceType: Optional[Annotated[str, AfterValidator(validate_instance_type)]] = None
    loadBalancerConfig: Optional[LoadBalancerConfig] = None
    modelId: str
    modelName: str
    modelType: ModelType
    modelUrl: Optional[str] = None
    status: ModelStatus
    streaming: bool


class ApiResponseBase(BaseModel):
    """Common API response definition for most API calls."""

    model: LISAModel


class CreateModelRequest(BaseModel):
    """Request object when creating a new model."""

    autoScalingConfig: Optional[AutoScalingConfig] = None
    containerConfig: Optional[ContainerConfig] = None
    inferenceContainer: Optional[InferenceContainer] = None
    instanceType: Optional[Annotated[str, AfterValidator(validate_instance_type)]] = None
    loadBalancerConfig: Optional[LoadBalancerConfig] = None
    modelId: str
    modelName: str
    modelType: ModelType
    modelUrl: Optional[str] = None
    streaming: Optional[bool] = False

    @model_validator(mode="after")  # type: ignore
    def validate_create_model_request(self) -> Self:
        """Validate whole request object."""
        # Validate that an embedding model cannot be set as streaming-enabled
        if self.modelType == ModelType.EMBEDDING and self.streaming:
            raise ValueError("Embedding model cannot be set with streaming enabled.")
        return self


class CreateModelResponse(ApiResponseBase):
    """Response object when creating a model."""

    pass


class ListModelsResponse(BaseModel):
    """Response object when listing models."""

    models: List[LISAModel]


class GetModelResponse(ApiResponseBase):
    """Response object when getting a model."""

    pass


class UpdateModelRequest(BaseModel):
    """Request object when updating a model."""

    autoScalingInstanceConfig: Optional[AutoScalingInstanceConfig] = None
    enabled: Optional[bool] = None
    modelType: Optional[ModelType] = None
    streaming: Optional[bool] = None

    @model_validator(mode="after")  # type: ignore
    def validate_update_model_request(self) -> Self:
        """Validate whole request object."""
        fields = (
            self.autoScalingInstanceConfig,
            self.enabled,
            self.modelType,
            self.streaming,
        )
        # Validate that at minimum one field is defined, otherwise there's no action to take in this update
        if all((field is None for field in fields)):
            raise ValueError(
                "At least one field out of 'autoScalingInstanceConfig', 'enabled', 'modelType', or "
                "'streaming' must be defined in request payload."
            )

        # Validate that an embedding model cannot be set as streaming-enabled
        if self.modelType == ModelType.EMBEDDING and self.streaming:
            raise ValueError("Embedding model cannot be set with streaming enabled.")
        return self

    @field_validator("autoScalingInstanceConfig")  # type: ignore
    @classmethod
    def validate_autoscaling_instance_config(cls, config: AutoScalingInstanceConfig) -> AutoScalingInstanceConfig:
        """Validate that the AutoScaling instance config has at least one positive value."""
        if not config:
            raise ValueError("The autoScalingInstanceConfig must not be null if defined in request payload.")
        config_fields = (config.minCapacity, config.maxCapacity, config.desiredCapacity)
        if all((field is None for field in config_fields)):
            raise ValueError("At least one option of autoScalingInstanceConfig must be defined.")
        if any((isinstance(field, int) and field < 1 for field in config_fields)):
            raise ValueError("All autoScalingInstanceConfig fields must be >= 1.")
        # if desired and max are greater than 1, and desired is greater than requested max, throw error
        if config.desiredCapacity and config.maxCapacity and config.desiredCapacity > config.maxCapacity:
            raise ValueError("Desired capacity must be <= max capacity.")
        # if desired and min are 0 or more, and desired is less than requested min, throw error
        if isinstance(config.desiredCapacity, int) and isinstance(config.minCapacity, int):
            if config.desiredCapacity < config.minCapacity:
                raise ValueError("Desired capacity must be >= min capacity.")
        return config


class UpdateModelResponse(ApiResponseBase):
    """Response object when updating a model."""

    pass


class DeleteModelResponse(ApiResponseBase):
    """Response object when deleting a model."""

    pass
