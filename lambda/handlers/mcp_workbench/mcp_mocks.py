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

"""Mock implementations of MCP Workbench core components for validation purposes.

These mocks are used by the syntax validator to allow user code to import
and use MCP Workbench constructs without needing the full MCP Workbench
package installed. They provide just enough functionality to validate
the structure and usage of MCP tools.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import wraps
from typing import Any


class BaseTool(ABC):
    """
    Mock BaseTool for validation purposes.

    This provides the same interface as the real BaseTool class,
    allowing validation of class-based MCP tools without requiring
    the full MCP Workbench package.
    """

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
        Returns a function to be executed as the tool.

        Returns:
            The function to be executed
        """
        pass


def mcp_tool(name: str, description: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Mock mcp_tool decorator for validation purposes.

    This provides the same interface as the real mcp_tool decorator,
    allowing validation of function-based MCP tools without requiring
    the full MCP Workbench package.

    Args:
        name: The name of the tool
        description: A description of what the tool does

    Returns:
        The decorated function with MCP tool metadata
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        # Store metadata as function attributes
        func._mcp_tool_name = name  # type: ignore[attr-defined]
        func._mcp_tool_description = description  # type: ignore[attr-defined]
        func._is_mcp_tool = True  # type: ignore[attr-defined]

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # If the function is already async, await it
            if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:  # CO_COROUTINE
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        # Copy metadata to wrapper
        wrapper._mcp_tool_name = name  # type: ignore[attr-defined]
        wrapper._mcp_tool_description = description  # type: ignore[attr-defined]
        wrapper._is_mcp_tool = True  # type: ignore[attr-defined]
        wrapper._original_func = func  # type: ignore[attr-defined]

        return wrapper

    return decorator
