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
from pydantic.functional_validators import AfterValidator
from utilities.validators import validate_instance_type


class InferenceContainer(str, Enum):
    """Enum representing the interface container type."""

    def __str__(self) -> str:
        """Represent the enum as a string."""
        return str(self.value)

    TGI = "tgi"
    TEI = "tei"
    VLLM = "vllm"
    INSTRUCTOR = "instructor"


class ModelStatus(str, Enum):
    """Enum representing a model status."""

    def __str__(self) -> str:
        """Represent the enum as a string."""
        return str(self.value)

    CREATING = "Creating"
    IN_SERVICE = "InService"
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

    AlbMetricName: str
    TargetValue: int
    Duration: int
    EstimatedInstanceWarmup: int


class LoadBalancerHealthCheckConfig(BaseModel):
    """Health check configuration for a load balancer."""

    Path: str
    Interval: int
    Timeout: int
    HealthyThresholdCount: int
    UnhealthyThresholdCount: int


class LoadBalancerConfig(BaseModel):
    """Load balancer configuration."""

    HealthCheckConfig: LoadBalancerHealthCheckConfig


class AutoScalingConfig(BaseModel):
    """Autoscaling configuration."""

    MinCapacity: int
    MaxCapacity: int
    Cooldown: int
    DefaultInstanceWarmup: int
    MetricConfig: MetricConfig


class ContainerHealthCheckConfig(BaseModel):
    """Health check configuration for a container."""

    Command: Union[str, list[str]]
    Interval: int
    StartPeriod: int
    Timeout: int
    Retries: int


class ContainerConfigImage(BaseModel):
    """Image image configuration for a container."""

    BaseImage: str
    Path: str
    Type: str


class ContainerConfig(BaseModel):
    """Container configuration."""

    BaseImage: ContainerConfigImage
    SharedMemorySize: int
    HealthCheckConfig: ContainerHealthCheckConfig
    Environment: dict[str, str]


class LISAModel(BaseModel):
    """Core model definition fields."""

    AutoScalingConfig: Optional[AutoScalingConfig]
    ContainerConfig: Optional[ContainerConfig]
    LoadBalancerConfig: Optional[LoadBalancerConfig]
    ModelId: str
    ModelName: str
    ModelType: ModelType
    ModelUrl: Optional[str]
    Status: ModelStatus
    Streaming: bool
    UniqueId: str


class ApiResponseBase(BaseModel):
    """Common API response definition for most API calls."""

    Model: LISAModel


class CreateModelRequest(BaseModel):
    """Request object when creating a new model."""

    AutoScalingConfig: Optional[AutoScalingConfig]
    ContainerConfig: Optional[ContainerConfig]
    InferenceContainer: Optional[InferenceContainer]
    InstanceType: Optional[Annotated[str, AfterValidator(validate_instance_type)]]
    LoadBalancerConfig: Optional[LoadBalancerConfig]
    ModelId: str
    ModelName: str
    ModelType: ModelType
    ModelUrl: Optional[str]
    Streaming: bool


class CreateModelResponse(ApiResponseBase):
    """Response object when creating a model."""

    pass


class ListModelsResponse(BaseModel):
    """Response object when listing models."""

    Models: List[LISAModel]


class GetModelResponse(ApiResponseBase):
    """Response object when getting a model."""

    pass


class UpdateModelRequest(BaseModel):
    """Request object when updating a model."""

    AutoScalingConfig: Optional[AutoScalingConfig]
    ContainerConfig: Optional[ContainerConfig]
    InferenceContainer: Optional[InferenceContainer]
    InstanceType: Optional[Annotated[str, AfterValidator(validate_instance_type)]]
    LoadBalancerConfig: Optional[LoadBalancerConfig]
    ModelId: Optional[str]
    ModelName: Optional[str]
    ModelType: Optional[ModelType]
    Streaming: Optional[bool]


class UpdateModelResponse(ApiResponseBase):
    """Response object when updating a model."""

    pass


class StartModelResponse(ApiResponseBase):
    """Response object when stopping a model."""

    pass


class StopModelResponse(ApiResponseBase):
    """Response object when stopping a model."""

    pass


class DeleteModelResponse(ApiResponseBase):
    """Response object when deleting a model."""

    pass
