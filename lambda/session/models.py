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

"""Pydantic models for session API requests and responses."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from utilities.encoders import convert_float_to_decimal
from utilities.time import iso_string

# --- Session configuration models (aligned with chat.configurations.model.ts) ---

ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh"]


class ModelArgs(BaseModel):
    """Model generation arguments (ISessionConfiguration.modelArgs)."""

    model_config = ConfigDict(extra="ignore")

    n: int | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    temperature: float | None = None
    seed: int | None = None
    stop: list[str] = Field(default_factory=list)
    reasoning_effort: ReasoningEffort | None = None


class ImageGenerationArgs(BaseModel):
    """Image generation arguments (ISessionConfiguration.imageGenerationArgs)."""

    model_config = ConfigDict(extra="ignore")

    size: str = "1024x1024"
    numberOfImages: int = 1
    quality: str = "standard"


class VideoGenerationArgs(BaseModel):
    """Video generation arguments (ISessionConfiguration.videoGenerationArgs)."""

    model_config = ConfigDict(extra="ignore")

    seconds: str = "4"
    size: str = "720x1280"


class SessionConfiguration(BaseModel):
    """Session configuration (ISessionConfiguration from chat.configurations.model.ts)."""

    model_config = ConfigDict(extra="ignore")

    markdownDisplay: bool = True
    streaming: bool = False
    showMetadata: bool = False
    showReasoningContent: bool = True
    max_tokens: int | None = None
    chatHistoryBufferSize: int = 7
    ragTopK: int = 3
    modelArgs: ModelArgs = Field(default_factory=ModelArgs)
    imageGenerationArgs: ImageGenerationArgs = Field(default_factory=ImageGenerationArgs)
    videoGenerationArgs: VideoGenerationArgs = Field(default_factory=VideoGenerationArgs)
    remixVideoId: str | None = None


class PromptConfiguration(BaseModel):
    """Prompt configuration (IPromptConfiguration from chat.configurations.model.ts)."""

    model_config = ConfigDict(extra="ignore")

    promptTemplate: str = ""


class ChatConfiguration(BaseModel):
    """Chat configuration (IChatConfiguration = promptConfiguration + sessionConfiguration)."""

    model_config = ConfigDict(extra="ignore")

    promptConfiguration: PromptConfiguration = Field(default_factory=PromptConfiguration)
    sessionConfiguration: SessionConfiguration = Field(default_factory=SessionConfiguration)


# --- RAG config (aligned with RagOptions.tsx RagConfig) ---
# Session stores partial snapshots; all fields optional for empty {}


class RagCollectionRef(BaseModel):
    """Minimal collection reference for session RAG config snapshot."""

    model_config = ConfigDict(extra="ignore")

    collectionId: str | None = None
    name: str | None = None


class RagConfig(BaseModel):
    """RAG configuration (RagConfig from RagOptions.tsx)."""

    model_config = ConfigDict(extra="ignore")

    collection: RagCollectionRef | dict[str, Any] | None = None
    embeddingModel: dict[str, Any] | None = None
    repositoryId: str | None = None
    repositoryType: str | None = None


# --- Selected model (session snapshot of IModel) ---


class SelectedModelFeature(BaseModel):
    """Model feature (ModelFeature from model-management.model.ts)."""

    model_config = ConfigDict(extra="ignore")

    name: str = ""
    overview: str = ""


class SelectedModel(BaseModel):
    """Selected model snapshot (IModel subset for session storage)."""

    model_config = ConfigDict(extra="ignore")

    modelId: str = ""
    modelName: str = ""
    modelType: str = "textgen"
    modelUrl: str = ""
    modelDescription: str | None = None
    status: str | None = None
    streaming: bool = True
    features: list[SelectedModelFeature] = Field(default_factory=list)
    allowedGroups: list[str] | None = None
    containerConfig: dict[str, Any] | None = None
    inferenceContainer: str | None = None
    instanceType: str | None = None
    autoScalingConfig: dict[str, Any] | None = None
    loadBalancerConfig: dict[str, Any] | None = None
    guardrailsConfig: dict[str, Any] | None = None


# --- Full session configuration (IChatConfiguration + IModelConfiguration) ---


class SessionConfigurationModel(BaseModel):
    """Full session configuration stored with each session."""

    model_config = ConfigDict(extra="ignore")

    sessionConfiguration: SessionConfiguration | None = None
    promptConfiguration: PromptConfiguration | None = None
    ragConfig: RagConfig | None = None
    selectedModel: SelectedModel | None = None
    chatAssistantId: str | None = None

    def model_dump_for_storage(self) -> dict[str, Any]:
        """Serialize to dict for DynamoDB storage."""
        result: dict[str, Any] = self.model_dump(mode="json", exclude_none=False)
        converted: dict[str, Any] = convert_float_to_decimal(result)
        return converted

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "SessionConfigurationModel":
        """Parse configuration from dict (e.g. DynamoDB or API payload)."""
        if not data:
            return cls()
        try:
            instance: SessionConfigurationModel = cls.model_validate(data)
            return instance
        except Exception:
            return cls()


# --- Session models ---


class SessionData(BaseModel):
    """Session data model for DynamoDB storage."""

    history: list[dict[str, Any]]
    name: str | None
    configuration: SessionConfigurationModel
    startTime: str
    createTime: str
    lastUpdated: str


class EncryptedSessionData(BaseModel):
    """Encrypted session data model for DynamoDB storage."""

    encrypted_history: str
    name: str | None
    encrypted_configuration: str
    startTime: str
    createTime: str
    lastUpdated: str
    encryption_version: str = "1.0"
    is_encrypted: bool = True


class Session(BaseModel):
    """Full session model from DynamoDB."""

    sessionId: str
    userId: str
    history: list[dict[str, Any]] = Field(default_factory=list)
    name: str | None = None
    configuration: SessionConfigurationModel = Field(default_factory=SessionConfigurationModel)
    startTime: str | None = None
    createTime: str | None = None
    lastUpdated: str | None = None

    @classmethod
    def from_dynamodb_item(cls, item: dict[str, Any]) -> "Session":
        """Create a Session from a DynamoDB item."""
        return cls(
            sessionId=item.get("sessionId", ""),
            userId=item.get("userId", ""),
            history=item.get("history", []),
            name=item.get("name"),
            configuration=SessionConfigurationModel.from_dict(item.get("configuration")),
            startTime=item.get("startTime"),
            createTime=item.get("createTime"),
            lastUpdated=item.get("lastUpdated"),
        )


class SessionSummary(BaseModel):
    """Summary of a session for list responses."""

    sessionId: str | None = None
    name: str | None = None
    firstHumanMessage: str = ""
    startTime: str | None = None
    createTime: str | None = None
    lastUpdated: str | None = None
    isEncrypted: bool = False


class PutSessionRequest(BaseModel):
    """Request model for updating a session with messages and configuration."""

    messages: list[dict[str, Any]] = Field(description="List of message objects representing the session history")
    configuration: SessionConfigurationModel | None = Field(
        default=None,
        description="Optional session configuration including selected model settings",
    )
    name: str | None = Field(default=None, description="Optional session name")

    @field_validator("configuration", mode="before")
    @classmethod
    def _parse_configuration(cls, v: Any) -> SessionConfigurationModel | None:
        if v is None:
            return None
        if isinstance(v, SessionConfigurationModel):
            return v
        if isinstance(v, dict):
            return SessionConfigurationModel.from_dict(v)
        return None

    def to_session_data(
        self,
        configuration: SessionConfigurationModel | None = None,
    ) -> SessionData:
        """Convert request to session data for DynamoDB storage."""
        timestamp = iso_string()
        config = configuration if configuration is not None else (self.configuration or SessionConfigurationModel())
        return SessionData(
            history=self.messages,
            name=self.name,
            configuration=config,
            startTime=timestamp,
            createTime=timestamp,
            lastUpdated=timestamp,
        )


class RenameSessionRequest(BaseModel):
    """Request model for renaming a session."""

    name: str = Field(description="New session name")


class AttachImageRequest(BaseModel):
    """Request model for attaching an image to a session."""

    message: dict[str, Any] = Field(description="Message object containing image data")
