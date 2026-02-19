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

"""Pydantic models for Chat Assistant Stacks."""
import uuid

from pydantic import BaseModel, Field
from utilities.time import iso_string


class ChatAssistantStackModel(BaseModel):
    """Model for a Chat Assistant Stack stored in DynamoDB."""

    stackId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    modelIds: list[str] = Field(default_factory=list)
    repositoryIds: list[str] = Field(default_factory=list)
    collectionIds: list[str] = Field(default_factory=list)
    mcpServerIds: list[str] = Field(default_factory=list)
    mcpToolIds: list[str] = Field(default_factory=list)
    personaPromptId: str | None = None
    directivePromptIds: list[str] = Field(default_factory=list)
    allowedGroups: list[str] = Field(default_factory=list)
    isActive: bool = True
    created: str | None = Field(default_factory=iso_string)
    updated: str | None = Field(default_factory=iso_string)
