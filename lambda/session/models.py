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

from typing import Any

from pydantic import BaseModel, Field
from utilities.time import iso_string


class SessionData(BaseModel):
    """Session data model for DynamoDB storage."""

    history: list[dict[str, Any]]
    name: str | None
    configuration: dict[str, Any]
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
    configuration: dict[str, Any] = Field(default_factory=dict)
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
            configuration=item.get("configuration", {}),
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
    configuration: dict[str, Any] | None = Field(
        default=None, description="Optional session configuration including selected model settings"
    )
    name: str | None = Field(default=None, description="Optional session name")

    def to_session_data(self, configuration: dict[str, Any] | None = None) -> SessionData:
        """Convert request to session data for DynamoDB storage."""
        timestamp = iso_string()
        return SessionData(
            history=self.messages,
            name=self.name,
            configuration=configuration if configuration is not None else (self.configuration or {}),
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
