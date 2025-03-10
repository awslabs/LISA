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

import logging
import time
import uuid
from enum import Enum
from typing import Annotated, Any, Dict, Generator, List, Optional, TypeAlias, Union

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, PositiveInt
from pydantic.functional_validators import AfterValidator, field_validator, model_validator
from typing_extensions import Self
from utilities.validators import validate_all_fields_defined, validate_any_fields_defined, validate_instance_type

logger = logging.getLogger(__name__)


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
    targetValue: NonNegativeInt
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

    blockDeviceVolumeSize: Optional[NonNegativeInt] = 30
    minCapacity: NonNegativeInt
    maxCapacity: NonNegativeInt
    cooldown: PositiveInt
    defaultInstanceWarmup: PositiveInt
    metricConfig: MetricConfig

    @model_validator(mode="after")
    def validate_auto_scaling_config(self) -> Self:
        """Validate autoScalingConfig values."""
        if self.minCapacity > self.maxCapacity:
            raise ValueError("minCapacity must be less than or equal to the maxCapacity.")
        if self.blockDeviceVolumeSize is not None and self.blockDeviceVolumeSize < 30:
            raise ValueError("blockDeviceVolumeSize must be greater than or equal to 30.")
        return self


class AutoScalingInstanceConfig(BaseModel):
    """Autoscaling instance count configuration upon model update."""

    minCapacity: Optional[PositiveInt] = None
    maxCapacity: Optional[PositiveInt] = None
    desiredCapacity: Optional[PositiveInt] = None

    @model_validator(mode="after")
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
    interval: PositiveInt
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

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, environment: Dict[str, str]) -> Dict[str, str]:
        """Validate that all keys in Dict are not empty."""
        if environment:
            if not all((key for key in environment.keys())):
                raise ValueError("Empty strings are not allowed for environment variable key names.")
        return environment


class ModelFeature(BaseModel):
    __exceptions: List[Any] = []
    name: str
    overview: str

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


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
    features: Optional[List[ModelFeature]] = None


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
    features: Optional[List[ModelFeature]] = None

    @model_validator(mode="after")
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

    @model_validator(mode="after")
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

    @field_validator("autoScalingInstanceConfig")
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


class IngestionType(Enum):
    AUTO = "auto"
    MANUAL = "manual"


RagDocumentDict: TypeAlias = Dict[str, Any]


class ChunkStrategyType(Enum):
    """Enum for different types of chunking strategies."""

    FIXED = "fixed"


class RagSubDocument(BaseModel):
    """Rag Sub-Document Entity for storing in DynamoDB."""

    document_id: str
    subdocs: list[str] = Field(default_factory=lambda: [])
    index: int = Field(exclude=True)
    sk: Optional[str] = None

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self.sk = f"subdoc#{self.document_id}#{self.index}"


class RagDocument(BaseModel):
    """Rag Document Entity for storing in DynamoDB."""

    pk: Optional[str] = None
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repository_id: str
    collection_id: str
    document_name: str
    source: str
    username: str
    subdocs: List[str] = Field(default_factory=lambda: [], exclude=True)
    chunk_strategy: dict[str, str] = {}
    ingestion_type: IngestionType = Field(default_factory=lambda: IngestionType.MANUAL)
    upload_date: int = Field(default_factory=lambda: int(time.time() * 1000))
    chunks: Optional[int] = 0
    model_config = ConfigDict(use_enum_values=True, validate_default=True)

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self.pk = self.createPartitionKey(self.repository_id, self.collection_id)
        self.chunks = len(self.subdocs)

    @staticmethod
    def createPartitionKey(repository_id: str, collection_id: str) -> str:
        return f"{repository_id}#{collection_id}"

    def chunk_doc(self, chunk_size: int = 1000) -> Generator[RagSubDocument, None, None]:
        """Chunk the document into smaller sub-documents."""
        total_subdocs = len(self.subdocs)
        for start_index in range(0, total_subdocs, chunk_size):
            end_index = min(start_index + chunk_size, total_subdocs)
            yield RagSubDocument(
                document_id=self.document_id, subdocs=self.subdocs[start_index:end_index], index=start_index
            )

    @staticmethod
    def join_docs(documents: List[RagDocumentDict]) -> List[RagDocumentDict]:
        """Join the multiple sub-documents into a single document."""
        # Group documents by document_id
        grouped_docs: dict[str, List[RagDocumentDict]] = {}
        for doc in documents:
            doc_id = doc.get("document_id", "")
            if doc_id not in grouped_docs:
                grouped_docs[doc_id] = []
            grouped_docs[doc_id].append(doc)

        # Join same document_id into single RagDocument
        joined_docs: List[RagDocumentDict] = []
        for docs in grouped_docs.values():
            joined_doc = docs[0]
            joined_doc["subdocs"] = [sub_doc for doc in docs for sub_doc in (doc.get("subdocs", []) or [])]
            joined_docs.append(joined_doc)

        return joined_docs
