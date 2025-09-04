"""Example function-based MCP tools for text manipulation."""

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
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to count characters for"
            }
        },
        "required": ["text"]
    }
)
async def count_characters(text: str):
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
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to transform"
            },
            "transformation": {
                "type": "string",
                "enum": ["upper", "lower", "title", "capitalize"],
                "description": "The type of transformation to apply"
            }
        },
        "required": ["text", "transformation"]
    }
)
def transform_text(text: str, transformation: str):
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
    parameters={
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to reverse"
            }
        },
        "required": ["text"]
    }
)
def reverse_text(text: str):
    """Reverse the characters in the given text."""
    return {
        "original": text,
        "reversed": text[::-1]
    }
