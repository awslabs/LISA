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

"""Example function-based MCP tools for text manipulation."""

from typing import Annotated

# Note: In a real deployment, you would need to ensure mcpworkbench is available
# For development, you might need to adjust the import path or install the package
try:
    from mcpworkbench.core.annotations import mcp_tool
except ImportError:
    # Fallback for development - adjust path as needed
    import os
    import sys

    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from mcpworkbench.core.annotations import mcp_tool


@mcp_tool(
    name="text_length",
    description="Count the number of characters in a text string",
)
async def count_characters(text: Annotated[str, "The text string to analyze"]):
    """Count the number of characters in the given text."""
    return {
        "text": text,
        "character_count": len(text),
        "word_count": len(text.split()),
        "line_count": len(text.splitlines()),
    }


@mcp_tool(
    name="text_transform",
    description="Transform text to uppercase, lowercase, or title case",
)
def transform_text(
    text: Annotated[str, "The text string to transform"],
    transformation: Annotated[str, "Type of transformation: 'upper', 'lower', 'title', or 'capitalize'"],
):
    """Transform the given text according to the specified transformation."""
    if transformation == "upper":
        result = text.upper()
    elif transformation == "lower":
        result = text.lower()
    elif transformation == "title":
        result = text.title()
    elif transformation == "capitalize":
        result = text.capitalize()
    else:
        raise ValueError(f"Unknown transformation: {transformation}")

    return {"original": text, "transformation": transformation, "result": result}


@mcp_tool(
    name="text_reverse",
    description="Reverse the characters in a text string",
)
def reverse_text(text: Annotated[str, "The text string to reverse"]):
    """Reverse the characters in the given text."""
    return {"original": text, "reversed": text[::-1]}
