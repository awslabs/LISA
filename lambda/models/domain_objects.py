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
from typing import Annotated, Union

from pydantic import BaseModel
from pydantic.functional_validators import AfterValidator
from utilities.validators import validate_instance_type


class InferenceContainer(str, Enum):
    """Enum representing the interface container type."""

    def __str__(self) -> str:
        """Represent the enum as a string."""
        return str(self.value)

    TGI = "TGI"
    TEI = "TEI"
    VLLM = "VLLM"
    INSTRUCTOR = "INSTRUCTOR"


class ModelStatus(str, Enum):
    """Enum representing a model status."""

    def __str__(self) -> str:
        """Represent the enum as a string."""
        return str(self.value)

    CREATING = "CREATING"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    UPDATING = "UPDATING"
    DELETING = "DELETING"


class ModelType(str, Enum):
    """Enum representing a model type."""

    def __str__(self) -> str:
        """Represent the enum as a string."""
        return str(self.value)

    TEXTGEN = ("TEXTGEN",)
    EMBEDDING = "EMBEDDING"


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


class CreateModelRequest(BaseModel):
    """Request object for creating a new model."""

    ModelId: str
    ModelName: str
    Streaming: bool
    ModelType: ModelType
    InferenceContainer: InferenceContainer
    InstanceType: Annotated[str, AfterValidator(validate_instance_type)]
    ContainerConfig: ContainerConfig
    AutoScalingConfig: AutoScalingConfig
    LoadBalancerConfig: LoadBalancerConfig


class CreateModelResponse(BaseModel):
    """Response object when creating a model."""

    ModelId: str
    ModelName: str
    Status: ModelStatus


class ListModelResponse(BaseModel):
    """Response object when listing a models."""

    ModelId: str
    ModelName: str
    Status: ModelStatus


class DescribeModelResponse(BaseModel):
    """Response object when describing a model."""

    ModelId: str
    ModelName: str
    Status: ModelStatus
    InferenceContainer: InferenceContainer
    InstanceType: str
    ContainerConfig: ContainerConfig
    AutoScalingConfig: AutoScalingConfig
    LoadBalancerConfig: LoadBalancerConfig

    @staticmethod
    def DUMMY(model_id: str, model_name: str, status: ModelStatus = ModelStatus.ACTIVE) -> "DescribeModelResponse":
        """
        Create a dummy object while the API is stubbed.

        This method is temporary and should be removed once the endpoints are no longer stubbed.
        """
        return DescribeModelResponse(
            ModelId=model_id,
            ModelName=model_name,
            Status=status,
            Streaming=True,
            ModelType=ModelType.TEXTGEN,
            InstanceType="m5.large",
            InferenceContainer=InferenceContainer.TGI,
            ContainerConfig=ContainerConfig(
                BaseImage=ContainerConfigImage(
                    BaseImage="ghcr.io/huggingface/text-generation-inference:2.0.1",
                    Path="lib/serve/ecs-model/textgen/tgi",
                    Type="asset",
                ),
                SharedMemorySize=2048,
                HealthCheckConfig=ContainerHealthCheckConfig(
                    Command=["CMD-SHELL", "exit 0"], Interval=10, StartPeriod=30, Timeout=5, Retries=5
                ),
                Environment={
                    "MAX_CONCURRENT_REQUESTS": "128",
                    "MAX_INPUT_LENGTH": "1024",
                    "MAX_TOTAL_TOKENS": "2048",
                },
            ),
            AutoScalingConfig=AutoScalingConfig(
                MinCapacity=1,
                MaxCapacity=1,
                Cooldown=420,
                DefaultInstanceWarmup=180,
                MetricConfig=MetricConfig(
                    AlbMetricName="RequestCountPerTarget", TargetValue=30, Duration=60, EstimatedInstanceWarmup=330
                ),
            ),
            LoadBalancerConfig=LoadBalancerConfig(
                HealthCheckConfig=LoadBalancerHealthCheckConfig(
                    Path="/health", Interval=60, Timeout=30, HealthyThresholdCount=2, UnhealthyThresholdCount=10
                )
            ),
        )


class UpdateModelRequest(BaseModel):
    """Requset object when updating a model."""

    ModelId: str
    ModelName: str
    Status: ModelStatus
    Streaming: bool
    ModelType: ModelType
    InstanceType: str
    InferenceContainer: InferenceContainer
    ContainerConfig: ContainerConfig
    AutoScalingConfig: AutoScalingConfig
    LoadBalancerConfig: LoadBalancerConfig

    @staticmethod
    def DUMMY(model_id: str, model_name: str, status: ModelStatus = ModelStatus.ACTIVE) -> "UpdateModelRequest":
        """
        Create a dummy object while the API is stubbed.

        This method is temporary and should be removed once the endpoints are no longer stubbed.
        """
        return UpdateModelRequest(
            ModelId=model_id,
            ModelName=model_name,
            Status=status,
            Streaming=True,
            ModelType=ModelType.TEXTGEN,
            InstanceType="m5.large",
            InferenceContainer=InferenceContainer.TGI,
            ContainerConfig=ContainerConfig(
                BaseImage=ContainerConfigImage(
                    BaseImage="ghcr.io/huggingface/text-generation-inference:2.0.1",
                    Path="lib/serve/ecs-model/textgen/tgi",
                    Type="asset",
                ),
                SharedMemorySize=2048,
                HealthCheckConfig=ContainerHealthCheckConfig(
                    Command=["CMD-SHELL", "exit 0"], Interval=10, StartPeriod=30, Timeout=5, Retries=5
                ),
                Environment={
                    "MAX_CONCURRENT_REQUESTS": "128",
                    "MAX_INPUT_LENGTH": "1024",
                    "MAX_TOTAL_TOKENS": "2048",
                },
            ),
            AutoScalingConfig=AutoScalingConfig(
                MinCapacity=1,
                MaxCapacity=1,
                Cooldown=420,
                DefaultInstanceWarmup=180,
                MetricConfig=MetricConfig(
                    AlbMetricName="RequestCountPerTarget", TargetValue=30, Duration=60, EstimatedInstanceWarmup=330
                ),
            ),
            LoadBalancerConfig=LoadBalancerConfig(
                HealthCheckConfig=LoadBalancerHealthCheckConfig(
                    Path="/health", Interval=60, Timeout=30, HealthyThresholdCount=2, UnhealthyThresholdCount=10
                )
            ),
        )


class DeleteModelResponse(BaseModel):
    """Response object when deleting a model."""

    ModelId: str
    ModelName: str
    Status: ModelStatus = ModelStatus.DELETING
