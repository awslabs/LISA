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

"""Annotations for function-based MCP tools."""

from functools import wraps
from typing import Any, Callable, Dict, TypeVar, cast

F = TypeVar("F", bound=Callable[..., Any])


def mcp_tool(name: str, description: str) -> Callable[[F], F]:
    """
    Decorator to mark a function as an MCP tool.

    Args:
        name: The name of the tool
        description: A description of what the tool does

    Returns:
        The decorated function with MCP tool metadata
    """

    def decorator(func: F) -> F:
        # Store metadata as function attributes
        func._mcp_tool_name = name  # type: ignore[attr-defined]
        func._mcp_tool_description = description  # type: ignore[attr-defined]
        func._is_mcp_tool = True  # type: ignore[attr-defined]

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # If the function is not already async, we need to handle it
            if hasattr(func, "__code__") and func.__code__.co_flags & 0x80:  # CO_COROUTINE
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)

        # Copy metadata to wrapper
        wrapper._mcp_tool_name = name  # type: ignore[attr-defined]
        wrapper._mcp_tool_description = description  # type: ignore[attr-defined]
        wrapper._is_mcp_tool = True  # type: ignore[attr-defined]
        wrapper._original_func = func  # type: ignore[attr-defined]

        return cast(F, wrapper)

    return decorator


def is_mcp_tool(func: Callable) -> bool:
    """Check if a function is marked as an MCP tool."""
    return hasattr(func, "_is_mcp_tool") and getattr(func, "_is_mcp_tool", False)


def get_tool_metadata(func: Callable) -> Dict[str, Any]:
    """Get the MCP tool metadata from a decorated function."""
    if not is_mcp_tool(func):
        raise ValueError("Function is not marked as an MCP tool")

    return {
        "name": getattr(func, "_mcp_tool_name", ""),
        "description": getattr(func, "_mcp_tool_description", ""),
    }
