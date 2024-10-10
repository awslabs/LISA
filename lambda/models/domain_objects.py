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

from decimal import Decimal
from enum import Enum
from typing import Annotated, Dict, List, Optional, Union

from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt
from pydantic.functional_validators import AfterValidator, field_validator, model_validator
from typing_extensions import Self
from utilities.validators import validate_all_fields_defined, validate_any_fields_defined, validate_instance_type


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

    albMetricName: str = Field(min_length=1)
    targetValue: Decimal
    duration: PositiveInt
    estimatedInstanceWarmup: PositiveInt


class LoadBalancerHealthCheckConfig(BaseModel):
    """Health check configuration for a load balancer."""

    path: str = Field(min_length=1)
    interval: PositiveInt
    timeout: PositiveInt
    healthyThresholdCount: PositiveInt
    unhealthyThresholdCount: PositiveInt


class LoadBalancerConfig(BaseModel):
    """Load balancer configuration."""

    healthCheckConfig: LoadBalancerHealthCheckConfig


class AutoScalingConfig(BaseModel):
    """Autoscaling configuration upon model creation."""

    minCapacity: NonNegativeInt
    maxCapacity: NonNegativeInt
    cooldown: PositiveInt
    defaultInstanceWarmup: PositiveInt
    metricConfig: MetricConfig

    @model_validator(mode="after")  # type: ignore
    def validate_auto_scaling_config(self) -> Self:
        """Validate autoScalingConfig values."""
        if self.minCapacity > self.maxCapacity:
            raise ValueError("minCapacity must be less than or equal to the maxCapacity.")
        return self


class AutoScalingInstanceConfig(BaseModel):
    """Autoscaling instance count configuration upon model update."""

    minCapacity: Optional[PositiveInt] = None
    maxCapacity: Optional[PositiveInt] = None
    desiredCapacity: Optional[PositiveInt] = None

    @model_validator(mode="after")  # type: ignore
    def validate_auto_scaling_instance_config(self) -> Self:
        """Validate autoScalingInstanceConfig values."""
        config_fields = [self.minCapacity, self.maxCapacity, self.desiredCapacity]
        if not validate_any_fields_defined(config_fields):
            raise ValueError("At least one option of autoScalingInstanceConfig must be defined.")
        # if desired and max are greater than 1, and desired is greater than requested max, throw error
        if self.desiredCapacity and self.maxCapacity and self.desiredCapacity > self.maxCapacity:
            raise ValueError("Desired capacity must be less than or equal to max capacity.")
        # if desired and min are 1 or more, and desired is less than requested min, throw error
        if self.desiredCapacity and self.minCapacity and self.desiredCapacity < self.minCapacity:
            raise ValueError("Desired capacity must be greater than or equal to minimum capacity.")
        return self


class ContainerHealthCheckConfig(BaseModel):
    """Health check configuration for a container."""

    command: Union[str, List[str]]
    interval: NonNegativeInt
    startPeriod: PositiveInt
    timeout: PositiveInt
    retries: PositiveInt


class ContainerConfigImage(BaseModel):
    """Image image configuration for a container."""

    baseImage: str = Field(min_length=1)
    type: str = Field(min_length=1)


class ContainerConfig(BaseModel):
    """Container configuration."""

    image: ContainerConfigImage
    sharedMemorySize: PositiveInt
    healthCheckConfig: ContainerHealthCheckConfig
    environment: Optional[Dict[str, str]] = {}

    @field_validator("environment")  # type: ignore
    @classmethod
    def validate_environment(cls, environment: Dict[str, str]) -> Dict[str, str]:
        """Validate that all keys in Dict are not empty."""
        if environment:
            if not all((key for key in environment.keys())):
                raise ValueError("Empty strings are not allowed for environment variable key names.")
        return environment


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
    modelId: str = Field(min_length=1)
    modelName: str = Field(min_length=1)
    modelType: ModelType
    modelUrl: Optional[str] = None
    streaming: Optional[bool] = False

    @model_validator(mode="after")  # type: ignore
    def validate_create_model_request(self) -> Self:
        """Validate whole request object."""
        # Validate that an embedding model cannot be set as streaming-enabled
        if self.modelType == ModelType.EMBEDDING and self.streaming:
            raise ValueError("Embedding model cannot be set with streaming enabled.")

        required_hosting_fields = [
            self.autoScalingConfig,
            self.containerConfig,
            self.inferenceContainer,
            self.instanceType,
            self.loadBalancerConfig,
        ]
        # If any of these fields are defined, assume LISA-hosted model. If LISA-hosted model, then ALL fields required.
        if validate_any_fields_defined(required_hosting_fields):
            if not validate_all_fields_defined(required_hosting_fields):
                raise ValueError(
                    "All of the following fields must be defined if creating a LISA-hosted model: "
                    "autoScalingConfig, containerConfig, inferenceContainer, instanceType, and loadBalancerConfig"
                )

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
        fields = [
            self.autoScalingInstanceConfig,
            self.enabled,
            self.modelType,
            self.streaming,
        ]
        # Validate that at minimum one field is defined, otherwise there's no action to take in this update
        if not validate_any_fields_defined(fields):
            raise ValueError(
                "At least one field out of autoScalingInstanceConfig, enabled, modelType, or "
                "streaming must be defined in request payload."
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
        return config


class UpdateModelResponse(ApiResponseBase):
    """Response object when updating a model."""

    pass


class DeleteModelResponse(ApiResponseBase):
    """Response object when deleting a model."""

    pass
