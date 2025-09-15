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
#   limitations under the License."""Base tool class and related data structures."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Optional, Union

from pydantic import BaseModel, Field


class ToolType(str, Enum):
    """Types of tools that can be discovered."""

    CLASS_BASED = "class_based"
    FUNCTION_BASED = "function_based"


class ToolInfo(BaseModel):
    """Information about a discovered tool."""

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    tool_type: ToolType = Field(..., description="Type of tool (class or function based)")
    file_path: str = Field(..., description="Path to the file containing the tool")
    module_name: str = Field(..., description="Python module name")

    # For class-based tools
    class_name: Optional[str] = Field(default=None, description="Class name for class-based tools")

    # For function-based tools
    function_name: Optional[str] = Field(default=None, description="Function name for function-based tools")

    # Tool instance or function reference (not serialized)
    tool_instance: Optional[Union[Any, Callable]] = Field(
        default=None, exclude=True, description="Tool instance or function"
    )


class BaseTool(ABC):
    """Abstract base class for MCP tools."""

    def __init__(self, name: str, description: str):
        """
        Initialize the tool with required metadata.

        Args:
            name: The name of the tool
            description: A description of what the tool does
        """
        self.name = name
        self.description = description

    @abstractmethod
    async def execute(self) -> Callable[..., Any]:
        """
        Returns an function to be executed as the tool.

        Returns:
            The function to be executed
        """
        pass
