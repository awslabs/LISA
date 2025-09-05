"""Example function-based MCP tools for text manipulation."""

from typing import Annotated

# Note: In a real deployment, you would need to ensure mcpworkbench is available
# For development, you might need to adjust the import path or install the package
try:
    from mcpworkbench.core.annotations import mcp_tool
except ImportError:
    # Fallback for development - adjust path as needed
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
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
        "line_count": len(text.splitlines())
    }


@mcp_tool(
    name="text_transform",
    description="Transform text to uppercase, lowercase, or title case",
)
def transform_text(
    text: Annotated[str, "The text string to transform"], 
    transformation: Annotated[str, "Type of transformation: 'upper', 'lower', 'title', or 'capitalize'"]
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
    
    return {
        "original": text,
        "transformation": transformation,
        "result": result
    }


@mcp_tool(
    name="text_reverse",
    description="Reverse the characters in a text string",
)
def reverse_text(text: Annotated[str, "The text string to reverse"]):
    """Reverse the characters in the given text."""
    return {
        "original": text,
        "reversed": text[::-1]
    }
