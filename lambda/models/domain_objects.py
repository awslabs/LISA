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
from pydantic import BaseModel
from pydantic.functional_validators import AfterValidator
from typing import Optional, Union
from utilities.validators import validate_instance_type
from enum import Enum
from typing import Annotated

class InferenceContainer(str, Enum):
    TGI = "TGI"
    TEI = "TEI"
    VLLM = "VLLM"
    INSTRUCTOR = "INSTRUCTOR"


class ModelStatus(str, Enum):
    CREATING = 'CREATING'
    READY    = 'READY'
    DELETED  = 'DELETED'


class MetricConfig(BaseModel):
    AlbMetricName: str
    TargetValue: int
    Duration: int
    EstimatedInstanceWarmup: int


class LoadBalancerHealthCheckConfig(BaseModel):
    Path: str
    Interval: int
    Timeout: int
    HealthyThresholdCount: int
    UnhealthyThresholdCount: int


class LoadBalancerConfig(BaseModel):
    HealthCheckConfig: LoadBalancerHealthCheckConfig


class AutoScalingConfig(BaseModel):
    MinCapacity: int
    MaxCapacity: int
    Cooldown: int
    DefaultInstanceWarmup: int
    MetricConfig: MetricConfig
    LoadBalancerConfig: LoadBalancerConfig


class ContainerHealthCheckConfig(BaseModel):
    Command: Union[str, list[str]]
    Interval: int
    StartPeriod: int
    Timeout: int
    Retries: int


class ContainerConfigImage(BaseModel):
    BaseImage: str
    Path: str
    Type: str


class ContainerConfig(BaseModel):
    BaseImage: ContainerConfigImage
    SharedMemorySize: int
    HealthCheckConfig: ContainerHealthCheckConfig
    Environment: dict[str, str]


class CreateModelResponse(BaseModel):
    ModelName: str
    Status: ModelStatus


class CreateModelRequest(BaseModel):
    ModelName: str
    ModelId: str
    InferenceContainer: Optional[InferenceContainer] = None
    InstanceType: Annotated[str, AfterValidator(validate_instance_type)]
    ContainerConfig: Optional[ContainerConfig] = None
    AutoScalingConfig: Optional[AutoScalingConfig] = None


class DeleteModelResponse(BaseModel):
    ModelName: str
    Status: str = "DELETED"


class GetModelResponse(BaseModel):
    ModelName: str