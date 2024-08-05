from enum import Enum
from typing import Optional
from pydantic import BaseModel

class InferenceContainer(str, Enum):
    TGI = "TGI"
    TEI = "TEI"
    VLLM = "VLLM"
    INSTRUCTOR = "INSTRUCTOR"

class ContainerConfigImage(BaseModel):
    BaseImage: str 
    Path: str 
    Type: str 

class HealthCheckConfig(BaseModel):
    Command: str | list[str]
    Interval: int
    StartPeriod: int
    Timeout: int
    Retries: int

class ContainerConfig(BaseModel):
    BaseImage: ContainerConfigImage
    SharedMemorySize: int
    HealthCheckConfig: HealthCheckConfig
    Environment: dict[str, str]

class MetricConfig(BaseModel):
    AlbMetricName: str
    TargetValue: int
    Duration: int
    EstimatedInstanceWarmup: int

class HealthCheckConfig(BaseModel):
    Path: str
    Interval: int
    Timeout: int
    HealthyThresholdCount: int
    UnhealthyThresholdCount: int

class LoadBalancerConfig(BaseModel):
    HealthCheckConfig: HealthCheckConfig

class AutoScalingConfig(BaseModel):
    MinCapacity: int
    MaxCapacity: int
    Cooldown: int
    DefaultInstanceWarmup: int
    MetricConfig: MetricConfig
    LoadBalancerConfig: LoadBalancerConfig

class CreateModelRequest(BaseModel):
    ModelName: str 
    ModelId: str 
    InferenceContainer: Optional[InferenceContainer] = None
    # todo: see if we can validate ec2 instance types
    InstanceType: str 
    ContainerConfig: Optional[ContainerConfig] = None
    AutoScalingConfig: Optional[AutoScalingConfig] = None

class ModelCreateStatus(str, Enum):
    CREATING = 'CREATING'

class CreateModelResponse(BaseModel):
    ModelName: str
    Status: ModelCreateStatus