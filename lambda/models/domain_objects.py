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
        ]
        if not validate_any_fields_defined(fields):
            raise ValueError(
                "At least one field out of autoScalingInstanceConfig, containerConfig, enabled, modelType, "
                "modelDescription, streaming, allowedGroups, or features must be defined in request payload."
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

    FIXED_SIZE = "FIXED_SIZE"
    FIXED = "fixed"  # Legacy support


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


class FixedSizeChunkingStrategy(BaseModel):
    """Defines parameters for fixed-size document chunking (new format)."""

    type: ChunkingStrategyType = ChunkingStrategyType.FIXED_SIZE
    chunkSize: int = Field(ge=100, le=10000, description="Size of each chunk in characters")
    chunkOverlap: int = Field(ge=0, description="Overlap between chunks in characters")

    @model_validator(mode="after")
    def validate_overlap(self) -> Self:
        """Validates that overlap is not greater than half the chunk size."""
        if self.chunkOverlap > self.chunkSize / 2:
            raise ValueError("chunkOverlap must be less than or equal to half of chunkSize")
        return self


ChunkingStrategy: TypeAlias = Union[FixedChunkingStrategy, FixedSizeChunkingStrategy]


# Future chunking strategies can be added here when implemented:
# 
# class SemanticChunkingStrategy(BaseModel):
#     """Defines parameters for semantic document chunking."""
#     type: ChunkingStrategyType = ChunkingStrategyType.SEMANTIC
#     threshold: float = Field(ge=0.0, le=1.0, description="Similarity threshold for semantic boundaries")
#     chunkSize: Optional[int] = Field(default=1000, ge=100, le=10000, description="Maximum chunk size")
#
# class RecursiveChunkingStrategy(BaseModel):
#     """Defines parameters for recursive document chunking."""
#     type: ChunkingStrategyType = ChunkingStrategyType.RECURSIVE
#     chunkSize: int = Field(ge=100, le=10000, description="Target size of each chunk")
#     chunkOverlap: int = Field(ge=0, description="Overlap between chunks")
#     separators: List[str] = Field(default_factory=lambda: ["\n\n", "\n", ". ", " "], description="Separators to use")
#
# To implement a new strategy:
# 1. Add the strategy type to ChunkingStrategyType enum
# 2. Create a strategy model class (like above)
# 3. Add it to the ChunkingStrategy TypeAlias union
# 4. Create a handler class extending ChunkingStrategyHandler in chunking_strategy_factory.py
# 5. Register the handler with ChunkingStrategyFactory.register_handler()


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
    embedding_model: Optional[str] = Field(default=None)
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


# ============================================================================
# Collection Management Models
# ============================================================================


class CollectionStatus(str, Enum):
    """Defines possible states for a collection."""

    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class PipelineTrigger(str, Enum):
    """Defines trigger types for collection pipelines."""

    EVENT = "event"
    SCHEDULE = "schedule"


class PipelineConfig(BaseModel):
    """Defines pipeline configuration for automated document ingestion."""

    autoRemove: bool = Field(default=True, description="Automatically remove documents after ingestion")
    chunkOverlap: int = Field(ge=0, description="Chunk overlap for pipeline ingestion")
    chunkSize: int = Field(ge=100, le=10000, description="Chunk size for pipeline ingestion")
    s3Bucket: str = Field(min_length=1, description="S3 bucket for pipeline source")
    s3Prefix: str = Field(description="S3 prefix for pipeline source")
    trigger: PipelineTrigger = Field(description="Pipeline trigger type")


class CollectionMetadata(BaseModel):
    """Defines metadata for a collection."""

    tags: List[str] = Field(default_factory=list, description="Metadata tags for the collection")
    customFields: Dict[str, Any] = Field(default_factory=dict, description="Custom metadata fields")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, tags: List[str]) -> List[str]:
        """Validates metadata tags."""
        if len(tags) > 50:
            raise ValueError("Maximum 50 tags allowed per collection")
        for tag in tags:
            if len(tag) > 50:
                raise ValueError("Each tag must be 50 characters or less")
            if not tag.replace("-", "").replace("_", "").isalnum():
                raise ValueError("Tags must contain only alphanumeric characters, hyphens, and underscores")
        return tags

    @classmethod
    def merge(cls, parent: Optional["CollectionMetadata"], child: Optional["CollectionMetadata"]) -> "CollectionMetadata":
        """Merges parent and child metadata.
        
        Args:
            parent: Parent vector store metadata
            child: Collection-specific metadata
            
        Returns:
            Merged metadata with combined tags and merged custom fields
        """
        if parent is None and child is None:
            return cls()
        if parent is None:
            return child or cls()
        if child is None:
            return parent
        
        # Combine tags (deduplicate while preserving order)
        merged_tags = list(dict.fromkeys(parent.tags + child.tags))
        
        # Merge custom fields (child overrides parent)
        merged_custom_fields = {**parent.customFields, **child.customFields}
        
        return cls(tags=merged_tags, customFields=merged_custom_fields)


class RagCollectionConfig(BaseModel):
    """Represents a RAG collection configuration."""

    collectionId: str = Field(default_factory=lambda: str(uuid4()), description="Unique collection identifier")
    repositoryId: str = Field(min_length=1, description="Parent vector store ID")
    name: Optional[str] = Field(default=None, max_length=100, description="User-friendly collection name")
    description: Optional[str] = Field(default=None, description="Collection description")
    chunkingStrategy: Optional[ChunkingStrategy] = Field(default=None, description="Chunking strategy for documents")
    allowChunkingOverride: bool = Field(
        default=True, description="Allow users to override chunking strategy during ingestion"
    )
    metadata: Optional[CollectionMetadata] = Field(default=None, description="Collection-specific metadata (merged with parent)")
    allowedGroups: Optional[List[str]] = Field(default=None, description="User groups with access to collection")
    embeddingModel: str = Field(min_length=1, description="Embedding model ID (can be set at creation, immutable after)")
    createdBy: str = Field(min_length=1, description="User ID of creator")
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Creation timestamp")
    updatedAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Last update timestamp")
    status: CollectionStatus = Field(default=CollectionStatus.ACTIVE, description="Collection status")
    private: bool = Field(default=False, description="Whether collection is private to creator")
    pipelines: List[PipelineConfig] = Field(default_factory=list, description="Automated ingestion pipelines")

    model_config = ConfigDict(use_enum_values=True, validate_default=True)

    @field_validator("name")
    @classmethod
    def validate_name(cls, name: Optional[str]) -> Optional[str]:
        """Validates collection name."""
        if name is not None:
            if len(name) > 100:
                raise ValueError("Collection name must be 100 characters or less")
            # Allow alphanumeric, spaces, hyphens, underscores
            if not all(c.isalnum() or c in " -_" for c in name):
                raise ValueError("Collection name must contain only alphanumeric characters, spaces, hyphens, and underscores")
        return name

    @field_validator("allowedGroups")
    @classmethod
    def validate_allowed_groups(cls, groups: Optional[List[str]]) -> Optional[List[str]]:
        """Validates allowed groups."""
        if groups is not None and len(groups) == 0:
            # Empty list should be treated as None (inherit from parent)
            return None
        return groups


class CreateCollectionRequest(BaseModel):
    """Request model for creating a new collection."""

    name: str = Field(min_length=1, max_length=100, description="Collection name (required)")
    description: Optional[str] = Field(default=None, description="Collection description")
    embeddingModel: Optional[str] = Field(
        default=None, description="Embedding model ID (inherits from parent if omitted, immutable after creation)"
    )
    chunkingStrategy: Optional[ChunkingStrategy] = Field(
        default=None, description="Chunking strategy (inherits from parent if omitted)"
    )
    allowedGroups: Optional[List[str]] = Field(
        default=None, description="User groups with access (inherits from parent if omitted)"
    )
    metadata: Optional[CollectionMetadata] = Field(
        default=None, description="Collection-specific metadata (merged with parent metadata)"
    )
    private: bool = Field(default=False, description="Whether collection is private to creator")
    allowChunkingOverride: bool = Field(default=True, description="Allow chunking strategy override during ingestion")
    pipelines: Optional[List[PipelineConfig]] = Field(default=None, description="Automated ingestion pipelines")


class UpdateCollectionRequest(BaseModel):
    """Request model for updating a collection."""

    name: Optional[str] = Field(default=None, max_length=100, description="Collection name")
    description: Optional[str] = Field(default=None, description="Collection description")
    chunkingStrategy: Optional[ChunkingStrategy] = Field(default=None, description="Chunking strategy")
    allowedGroups: Optional[List[str]] = Field(default=None, description="User groups with access")
    metadata: Optional[CollectionMetadata] = Field(default=None, description="Collection metadata")
    private: Optional[bool] = Field(default=None, description="Whether collection is private to creator")
    allowChunkingOverride: Optional[bool] = Field(
        default=None, description="Allow chunking strategy override during ingestion"
    )
    pipelines: Optional[List[PipelineConfig]] = Field(default=None, description="Automated ingestion pipelines")
    status: Optional[CollectionStatus] = Field(default=None, description="Collection status")

    @model_validator(mode="after")
    def validate_update_request(self) -> Self:
        """Validates that at least one field is provided for update."""
        fields = [
            self.name,
            self.description,
            self.chunkingStrategy,
            self.allowedGroups,
            self.metadata,
            self.private,
            self.allowChunkingOverride,
            self.pipelines,
            self.status,
        ]
        if not validate_any_fields_defined(fields):
            raise ValueError("At least one field must be provided for update")
        return self


class ListCollectionsResponse(PaginatedResponse):
    """Response model for listing collections."""

    collections: List[RagCollectionConfig] = Field(description="List of collections")
    totalCount: Optional[int] = Field(default=None, description="Total number of collections")
    currentPage: Optional[int] = Field(default=None, description="Current page number")
    totalPages: Optional[int] = Field(default=None, description="Total number of pages")


class CollectionSortBy(str, Enum):
    """Defines sort options for collection listing."""

    NAME = "name"
    CREATED_AT = "createdAt"
    UPDATED_AT = "updatedAt"


class SortOrder(str, Enum):
    """Defines sort order options."""

    ASC = "asc"
    DESC = "desc"


class RepositoryMetadata(BaseModel):
    """Defines metadata for a repository/vector store."""

    tags: List[str] = Field(default_factory=list, description="Tags for categorizing the repository")
    customFields: Optional[Dict[str, Any]] = Field(default=None, description="Custom metadata fields")


class VectorStoreConfig(BaseModel):
    """Represents a vector store/repository configuration."""

    repositoryId: str = Field(description="Unique identifier for the repository")
    repositoryName: Optional[str] = Field(default=None, description="User-friendly name for the repository")
    embeddingModelId: Optional[str] = Field(default=None, description="Default embedding model ID")
    type: str = Field(description="Type of vector store (opensearch, pgvector, bedrock_knowledge_base)")
    allowedGroups: List[str] = Field(default_factory=list, description="User groups with access to this repository")
    allowUserCollections: bool = Field(default=True, description="Whether non-admin users can create collections")
    metadata: Optional[RepositoryMetadata] = Field(default=None, description="Repository metadata")
    pipelines: Optional[List[PipelineConfig]] = Field(default=None, description="Automated ingestion pipelines")
    # Type-specific configurations
    opensearchConfig: Optional[Dict[str, Any]] = Field(default=None, description="OpenSearch configuration")
    rdsConfig: Optional[Dict[str, Any]] = Field(default=None, description="RDS/PGVector configuration")
    bedrockKnowledgeBaseConfig: Optional[Dict[str, Any]] = Field(
        default=None, description="Bedrock Knowledge Base configuration"
    )
    # Status and timestamps
    status: Optional[str] = Field(default=None, description="Repository status")
    createdAt: Optional[datetime] = Field(default=None, description="Creation timestamp")
    updatedAt: Optional[datetime] = Field(default=None, description="Last update timestamp")


class CreateVectorStoreRequest(BaseModel):
    """Request model for creating a new vector store."""

    repositoryId: str = Field(description="Unique identifier for the repository")
    repositoryName: Optional[str] = Field(default=None, description="User-friendly name")
    embeddingModelId: Optional[str] = Field(default=None, description="Default embedding model ID")
    type: str = Field(description="Type of vector store")
    allowedGroups: List[str] = Field(default_factory=list, description="User groups with access")
    allowUserCollections: bool = Field(default=True, description="Whether non-admin users can create collections")
    metadata: Optional[RepositoryMetadata] = Field(default=None, description="Repository metadata")
    pipelines: Optional[List[PipelineConfig]] = Field(default=None, description="Automated ingestion pipelines")
    opensearchConfig: Optional[Dict[str, Any]] = Field(default=None, description="OpenSearch configuration")
    rdsConfig: Optional[Dict[str, Any]] = Field(default=None, description="RDS/PGVector configuration")
    bedrockKnowledgeBaseConfig: Optional[Dict[str, Any]] = Field(
        default=None, description="Bedrock Knowledge Base configuration"
    )


class UpdateVectorStoreRequest(BaseModel):
    """Request model for updating a vector store."""

    repositoryName: Optional[str] = Field(default=None, description="User-friendly name")
    embeddingModelId: Optional[str] = Field(default=None, description="Default embedding model ID")
    allowedGroups: Optional[List[str]] = Field(default=None, description="User groups with access")
    allowUserCollections: Optional[bool] = Field(default=None, description="Whether non-admin users can create collections")
    metadata: Optional[RepositoryMetadata] = Field(default=None, description="Repository metadata")
    pipelines: Optional[List[PipelineConfig]] = Field(default=None, description="Automated ingestion pipelines")
