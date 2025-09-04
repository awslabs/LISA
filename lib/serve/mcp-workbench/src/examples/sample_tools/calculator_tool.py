"""Example class-based MCP tool for basic calculations."""

# Note: In a real deployment, you would need to ensure mcpworkbench is available
# For development, you might need to adjust the import path or install the package
try:
    from mcpworkbench.core.base_tool import BaseTool
except ImportError:
    # Fallback for development - adjust path as needed
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
    from mcpworkbench.core.base_tool import BaseTool


class CalculatorTool(BaseTool):
    """A simple calculator tool that performs basic arithmetic operations."""
    
    def __init__(self):
        super().__init__(
            name="calculator",
            description="Performs basic arithmetic operations (add, subtract, multiply, divide)"
        )
    
    def get_parameters(self):
        """Define the parameters schema for this tool."""
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["add", "subtract", "multiply", "divide"],
                    "description": "The arithmetic operation to perform"
                },
                "a": {
                    "type": "number",
                    "description": "The first number"
                },
                "b": {
                    "type": "number",
                    "description": "The second number"
                }
            },
            "required": ["operation", "a", "b"]
        }
    
    async def execute(self, **kwargs):
        """Execute the calculator operation."""
        operation = kwargs["operation"]
        a = float(kwargs["a"])
        b = float(kwargs["b"])
        
        if operation == "add":
            result = a + b
        elif operation == "subtract":
            result = a - b
        elif operation == "multiply":
            result = a * b
        elif operation == "divide":
            if b == 0:
                raise ValueError("Cannot divide by zero")
            result = a / b
        else:
            raise ValueError(f"Unknown operation: {operation}")
        
        return {
            "operation": operation,
            "a": a,
            "b": b,
            "result": result
        }
