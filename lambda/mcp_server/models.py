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

import uuid
from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class McpServerStatus(str, Enum):
    """Enum representing the prompt template type."""

    def __str__(self) -> str:
        """Represent the enum as a string."""
        return str(self.value)

    ACTIVE = "active"
    INACTIVE = "inactive"


class McpServerModel(BaseModel):
    """
    A Pydantic model representing a template for prompts.
    Contains metadata and functionality to create new revisions.
    """

    # Unique identifier for the mcp server
    id: Optional[str] = Field(default_factory=lambda: str(uuid.uuid4()))

    # Timestamp of when the mcp server was created
    created: Optional[str] = Field(default_factory=lambda: datetime.now().isoformat())

    # Owner of the MCP user
    owner: str

    # URL of the MCP server
    url: str

    # Name of the MCP server
    name: str

    # Description of the MCP server
    description: Optional[str] = Field(default_factory=lambda: None)

    # Custom headers for the MCP client
    customHeaders: Optional[dict] = Field(default_factory=lambda: None)

    # Custom client properties for the MCP client
    clientConfig: Optional[dict] = Field(default_factory=lambda: None)

    # Status of the server set by admins
    status: Optional[McpServerStatus] = Field(default=McpServerStatus.INACTIVE)

    # Groups of the MCP server
    groups: Optional[List[str]] = Field(default_factory=lambda: None)