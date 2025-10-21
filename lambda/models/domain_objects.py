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

"""Defines domain objects for model endpoint interactions."""

import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Dict, Generator, List, Optional, TypeAlias, Union
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, PositiveInt
from pydantic.functional_validators import AfterValidator, field_validator, model_validator
from typing_extensions import Self
from utilities.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, MIN_PAGE_SIZE
from utilities.validators import validate_all_fields_defined, validate_any_fields_defined, validate_instance_type

logger = logging.getLogger(__name__)


class InferenceContainer(str, Enum):
    """Defines supported inference container types."""

    def __str__(self) -> str:
        """Returns string representation of the enum value."""
        return str(self.value)

    TGI = "tgi"
    TEI = "tei"
    VLLM = "vllm"


class ModelStatus(str, Enum):
    """Defines possible model deployment states."""

    def __str__(self) -> str:
        """Returns string representation of the enum value."""
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
    """Defines supported model categories."""

    def __str__(self) -> str:
        """Returns string representation of the enum value."""
        return str(self.value)

    TEXTGEN = "textgen"
    IMAGEGEN = "imagegen"
    EMBEDDING = "embedding"


class GuardrailMode(str, Enum):
    """Defines supported guardrail execution modes."""

    def __str__(self) -> str:
        """Returns string representation of the enum value."""
        return str(self.value)

    PRE_CALL = "pre_call"
    DURING_CALL = "during_call"
    POST_CALL = "post_call"


class GuardrailConfig(BaseModel):
    """Defines configuration for a single guardrail."""

    guardrail_name: str = Field(min_length=1)
    guardrail_identifier: str = Field(min_length=1)
    guardrail_version: str = Field(default="DRAFT")
    mode: GuardrailMode = Field(default=GuardrailMode.PRE_CALL)
    description: Optional[str] = None
    allowed_groups: List[str] = Field(default_factory=list)
    marked_for_deletion: Optional[bool] = Field(default=False)

class GuardrailsConfig(BaseModel):
    """Defines configuration for multiple guardrails per model."""

    guardrails: Dict[str, GuardrailConfig] = Field(default_factory=dict)


class GuardrailRequest(BaseModel):
    """Defines request structure for guardrails API operations."""

    model_id: str = Field(min_length=1)
    guardrails_config: GuardrailsConfig


class GuardrailResponse(BaseModel):
    """Defines response structure for guardrails API operations."""

    model_id: str
    guardrails_config: GuardrailsConfig
    success: bool
    message: str


class GuardrailsTableEntry(BaseModel):
    """Represents a guardrail entry in DynamoDB table."""

    guardrail_id: str  # Partition key
    model_id: str  # Sort key
    guardrail_name: str
    guardrail_identifier: str
    guardrail_version: str
    mode: str
    description: Optional[str]
    allowed_groups: List[str]
    created_date: int = Field(default_factory=lambda: int(time.time() * 1000))
    last_modified_date: int = Field(default_factory=lambda: int(time.time() * 1000))


class MetricConfig(BaseModel):
    """Defines metrics configuration for auto-scaling policies."""

    albMetricName: str = Field(min_length=1)
    targetValue: NonNegativeInt
    duration: PositiveInt
    estimatedInstanceWarmup: PositiveInt


class LoadBalancerHealthCheckConfig(BaseModel):
    """Specifies health check parameters for load balancer configuration."""

    path: str = Field(min_length=1)
    interval: PositiveInt
    timeout: PositiveInt
    healthyThresholdCount: PositiveInt
    unhealthyThresholdCount: PositiveInt


class LoadBalancerConfig(BaseModel):
    """Defines load balancer settings."""

    healthCheckConfig: LoadBalancerHealthCheckConfig


class AutoScalingConfig(BaseModel):
    """Specifies auto-scaling parameters for model deployment."""

    blockDeviceVolumeSize: Optional[NonNegativeInt] = 50
    minCapacity: NonNegativeInt
    maxCapacity: NonNegativeInt
    cooldown: PositiveInt
    defaultInstanceWarmup: PositiveInt
    metricConfig: MetricConfig

    @model_validator(mode="after")
    def validate_auto_scaling_config(self) -> Self:
        """Validates auto-scaling configuration parameters."""
        if self.minCapacity > self.maxCapacity:
            raise ValueError("minCapacity must be less than or equal to the maxCapacity.")
        if self.blockDeviceVolumeSize is not None and self.blockDeviceVolumeSize < 30:
            raise ValueError("blockDeviceVolumeSize must be greater than or equal to 30.")
        return self


class AutoScalingInstanceConfig(BaseModel):
    """Defines instance count parameters for auto-scaling updates."""

    minCapacity: Optional[PositiveInt] = None
    maxCapacity: Optional[PositiveInt] = None
    desiredCapacity: Optional[PositiveInt] = None
    cooldown: Optional[PositiveInt] = None
    defaultInstanceWarmup: Optional[PositiveInt] = None

    @model_validator(mode="after")
    def validate_auto_scaling_instance_config(self) -> Self:
        """Validates auto-scaling instance configuration parameters."""
        config_fields = [
            self.minCapacity,
            self.maxCapacity,
            self.desiredCapacity,
            self.cooldown,
            self.defaultInstanceWarmup,
        ]
        if not validate_any_fields_defined(config_fields):
            raise ValueError("At least one option of autoScalingInstanceConfig must be defined.")
        if self.desiredCapacity and self.maxCapacity and self.desiredCapacity > self.maxCapacity:
            raise ValueError("Desired capacity must be less than or equal to max capacity.")
        if self.desiredCapacity and self.minCapacity and self.desiredCapacity < self.minCapacity:
            raise ValueError("Desired capacity must be greater than or equal to minimum capacity.")
        return self


class ContainerHealthCheckConfig(BaseModel):
    """Specifies container health check parameters."""

    command: Union[str, List[str]]
    interval: PositiveInt
    startPeriod: PositiveInt
    timeout: PositiveInt
    retries: PositiveInt


class ContainerConfigImage(BaseModel):
    """Defines container image configuration."""

    baseImage: str = Field(min_length=1)
    type: str = Field(min_length=1)


class ContainerConfig(BaseModel):
    """Specifies container deployment settings."""

    image: ContainerConfigImage
    sharedMemorySize: PositiveInt
    healthCheckConfig: ContainerHealthCheckConfig
    environment: Optional[Dict[str, str]] = {}

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, environment: Dict[str, str]) -> Dict[str, str]:
        """Validates environment variable key names."""
        if environment:
            if not all((key for key in environment.keys())):
                raise ValueError("Empty strings are not allowed for environment variable key names.")
        return environment


class ContainerConfigUpdatable(BaseModel):
    """Specifies container configuration fields that can be updated."""

    environment: Optional[Dict[str, str]] = None
    sharedMemorySize: Optional[PositiveInt] = None
    healthCheckCommand: Optional[Union[str, List[str]]] = None
    healthCheckInterval: Optional[PositiveInt] = None
    healthCheckTimeout: Optional[PositiveInt] = None
    healthCheckStartPeriod: Optional[PositiveInt] = None
    healthCheckRetries: Optional[PositiveInt] = None

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, environment: Dict[str, str]) -> Dict[str, str]:
        """Validates environment variable key names."""
        if environment:
            if not all((key for key in environment.keys())):
                raise ValueError("Empty strings are not allowed for environment variable key names.")
        return environment


class ModelFeature(BaseModel):
    """Defines model feature attributes."""

    __exceptions: List[Any] = []
    name: str
    overview: str

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


class LISAModel(BaseModel):
    """Defines core model attributes and configuration."""

    autoScalingConfig: Optional[AutoScalingConfig] = None
    containerConfig: Optional[ContainerConfig] = None
    inferenceContainer: Optional[InferenceContainer] = None
    instanceType: Optional[Annotated[str, AfterValidator(validate_instance_type)]] = None
    loadBalancerConfig: Optional[LoadBalancerConfig] = None
    modelId: str
    modelName: str
    modelDescription: Optional[str] = None
    modelType: ModelType
    modelUrl: Optional[str] = None
    status: ModelStatus
    streaming: bool
    features: Optional[List[ModelFeature]] = None
    allowedGroups: Optional[List[str]] = None


class ApiResponseBase(BaseModel):
    """Defines base structure for API responses."""

    model: LISAModel


class CreateModelRequest(BaseModel):
    """Specifies parameters for model creation requests."""

    autoScalingConfig: Optional[AutoScalingConfig] = None
    containerConfig: Optional[ContainerConfig] = None
    inferenceContainer: Optional[InferenceContainer] = None
    instanceType: Optional[Annotated[str, AfterValidator(validate_instance_type)]] = None
    loadBalancerConfig: Optional[LoadBalancerConfig] = None
    modelId: str = Field(min_length=1)
    modelName: str = Field(min_length=1)
    modelDescription: Optional[str] = None
    modelType: ModelType
    modelUrl: Optional[str] = None
    streaming: Optional[bool] = False
    features: Optional[List[ModelFeature]] = None
    allowedGroups: Optional[List[str]] = None
    apiKey: Optional[str] = None
    guardrailsConfig: Optional[GuardrailsConfig] = None

    @model_validator(mode="after")
    def validate_create_model_request(self) -> Self:
        """Validates model creation request parameters."""
        if self.modelType == ModelType.EMBEDDING and self.streaming:
            raise ValueError("Embedding model cannot be set with streaming enabled.")

        required_hosting_fields = [
            self.autoScalingConfig,
            self.containerConfig,
            self.inferenceContainer,
            self.instanceType,
            self.loadBalancerConfig,
        ]
        if validate_any_fields_defined(required_hosting_fields):
            if not validate_all_fields_defined(required_hosting_fields):
                raise ValueError(
                    "All of the following fields must be defined if creating a LISA-hosted model: "
                    "autoScalingConfig, containerConfig, inferenceContainer, instanceType, and loadBalancerConfig"
                )

        return self


class CreateModelResponse(ApiResponseBase):
    """Defines response structure for model creation."""

    pass


class ListModelsResponse(BaseModel):
    """Defines response structure for model listing."""

    models: List[LISAModel]


class GetModelResponse(ApiResponseBase):
    """Defines response structure for model retrieval."""

    pass


class UpdateModelRequest(BaseModel):
    """Specifies parameters for model update requests."""

    autoScalingInstanceConfig: Optional[AutoScalingInstanceConfig] = None
    enabled: Optional[bool] = None
    modelType: Optional[ModelType] = None
    modelDescription: Optional[str] = None
    streaming: Optional[bool] = None
    allowedGroups: Optional[List[str]] = None
    features: Optional[List[ModelFeature]] = None
    containerConfig: Optional[ContainerConfigUpdatable] = None
    guardrailsConfig: Optional[GuardrailsConfig] = None

    @model_validator(mode="after")
    def validate_update_model_request(self) -> Self:
        """Validates model update request parameters."""
        fields = [
            self.autoScalingInstanceConfig,
            self.enabled,
            self.modelType,
            self.modelDescription,
            self.streaming,
            self.allowedGroups,
            self.features,
            self.containerConfig,
            self.guardrailsConfig,
        ]
        if not validate_any_fields_defined(fields):
            raise ValueError(
                "At least one field out of autoScalingInstanceConfig, containerConfig, enabled, modelType, "
                "modelDescription, streaming, allowedGroups, features, or guardrailsConfig must be "
                "defined in request payload."
            )

        if self.modelType == ModelType.EMBEDDING and self.streaming:
            raise ValueError("Embedding model cannot be set with streaming enabled.")
        return self

    @field_validator("autoScalingInstanceConfig")
    @classmethod
    def validate_autoscaling_instance_config(cls, config: AutoScalingInstanceConfig) -> AutoScalingInstanceConfig:
        """Validates auto-scaling instance configuration."""
        if not config:
            raise ValueError("The autoScalingInstanceConfig must not be null if defined in request payload.")
        return config

    @field_validator("containerConfig")
    @classmethod
    def validate_container_config(cls, config: ContainerConfigUpdatable) -> ContainerConfigUpdatable:
        """Validates container configuration update."""
        if not config:
            raise ValueError("The containerConfig must not be null if defined in request payload.")
        return config


class UpdateModelResponse(ApiResponseBase):
    """Defines response structure for model updates."""

    pass


class DeleteModelResponse(ApiResponseBase):
    """Defines response structure for model deletion."""

    pass


class IngestionType(str, Enum):
    """Specifies whether ingestion was automatic or manual."""

    AUTO = "auto"
    MANUAL = "manual"


RagDocumentDict: TypeAlias = Dict[str, Any]


class ChunkingStrategyType(str, Enum):
    """Defines supported document chunking strategies."""

    FIXED = "fixed"


class IngestionStatus(str, Enum):
    """Defines possible states for document ingestion process."""

    INGESTION_PENDING = "INGESTION_PENDING"
    INGESTION_IN_PROGRESS = "INGESTION_IN_PROGRESS"
    INGESTION_COMPLETED = "INGESTION_COMPLETED"
    INGESTION_FAILED = "INGESTION_FAILED"

    DELETE_PENDING = "DELETE_PENDING"
    DELETE_IN_PROGRESS = "DELETE_IN_PROGRESS"
    DELETE_COMPLETED = "DELETE_COMPLETED"
    DELETE_FAILED = "DELETE_FAILED"


class FixedChunkingStrategy(BaseModel):
    """Defines parameters for fixed-size document chunking."""

    type: ChunkingStrategyType = ChunkingStrategyType.FIXED
    size: int
    overlap: int


ChunkingStrategy: TypeAlias = Union[FixedChunkingStrategy]


class RagSubDocument(BaseModel):
    """Represents a sub-document entity for DynamoDB storage."""

    document_id: str
    subdocs: list[str] = Field(default_factory=lambda: [])
    index: Optional[int] = Field(default=None)
    sk: Optional[str] = None

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self.sk = f"subdoc#{self.document_id}#{self.index}"


class RagDocument(BaseModel):
    """Represents a RAG document entity for DynamoDB storage."""

    pk: Optional[str] = None
    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repository_id: str
    collection_id: str
    document_name: str
    source: str
    username: str
    subdocs: List[str] = Field(default_factory=lambda: [], exclude=True)
    chunk_strategy: ChunkingStrategy
    ingestion_type: IngestionType = Field(default_factory=lambda: IngestionType.MANUAL)
    upload_date: int = Field(default_factory=lambda: int(time.time() * 1000))
    chunks: Optional[int] = 0
    model_config = ConfigDict(use_enum_values=True, validate_default=True)

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self.pk = self.createPartitionKey(self.repository_id, self.collection_id)
        # Only calculate chunks if not explicitly provided in data (for new documents)
        if "chunks" not in data:
            self.chunks = len(self.subdocs)

    @staticmethod
    def createPartitionKey(repository_id: str, collection_id: str) -> str:
        """Generates a partition key from repository and collection IDs."""
        return f"{repository_id}#{collection_id}"

    def chunk_doc(self, chunk_size: int = 1000) -> Generator[RagSubDocument, None, None]:
        """Segments document into smaller sub-documents."""
        total_subdocs = len(self.subdocs)
        for start_index in range(0, total_subdocs, chunk_size):
            end_index = min(start_index + chunk_size, total_subdocs)
            yield RagSubDocument(
                document_id=self.document_id, subdocs=self.subdocs[start_index:end_index], index=start_index
            )

    @staticmethod
    def join_docs(documents: List[RagDocumentDict]) -> List[RagDocumentDict]:
        """Combines multiple sub-documents into a single document."""
        grouped_docs: dict[str, List[RagDocumentDict]] = {}
        for doc in documents:
            doc_id = doc.get("document_id", "")
            if doc_id not in grouped_docs:
                grouped_docs[doc_id] = []
            grouped_docs[doc_id].append(doc)

        joined_docs: List[RagDocumentDict] = []
        for docs in grouped_docs.values():
            joined_doc = docs[0]
            joined_doc["subdocs"] = [sub_doc for doc in docs for sub_doc in (doc.get("subdocs", []) or [])]
            joined_docs.append(joined_doc)

        return joined_docs


class IngestionJob(BaseModel):
    """Represents an ingestion job entity for DynamoDB storage."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    s3_path: str
    collection_id: str
    document_id: Optional[str] = Field(default=None)
    repository_id: str
    chunk_strategy: Optional[ChunkingStrategy] = Field(default=None)
    username: Optional[str] = Field(default=None)
    status: IngestionStatus = IngestionStatus.INGESTION_PENDING
    created_date: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    error_message: Optional[str] = Field(default=None)
    document_name: Optional[str] = Field(default=None)
    auto: Optional[bool] = Field(default=None)

    def __init__(self, **data: Any) -> None:
        super().__init__(**data)

        self.document_name = self.s3_path.split("/")[-1] if self.s3_path else ""
        self.auto = self.username == "system"


class PaginatedResponse(BaseModel):
    """Base class for paginated API responses."""

    lastEvaluatedKey: Optional[Dict[str, str]] = None
    hasNextPage: bool = False
    hasPreviousPage: bool = False


class ListJobsResponse(PaginatedResponse):
    """Response structure for listing ingestion jobs with pagination."""

    jobs: List[IngestionJob]


@dataclass
class PaginationResult:
    """Result of pagination analysis."""

    has_next_page: bool
    has_previous_page: bool

    @classmethod
    def from_keys(
        cls, original_key: Optional[Dict[str, str]], returned_key: Optional[Dict[str, str]]
    ) -> "PaginationResult":
        """Create pagination result from keys."""
        return cls(has_next_page=returned_key is not None, has_previous_page=original_key is not None)


@dataclass
class PaginationParams:
    """Shared pagination parameter handling."""

    page_size: int = DEFAULT_PAGE_SIZE
    last_evaluated_key: Optional[Dict[str, str]] = None

    @staticmethod
    def parse_page_size(
        query_params: Dict[str, str], default: int = DEFAULT_PAGE_SIZE, max_size: int = MAX_PAGE_SIZE
    ) -> int:
        """Parse and validate page size with configurable limits."""
        page_size = int(query_params.get("pageSize", str(default)))
        return max(MIN_PAGE_SIZE, min(page_size, max_size))
