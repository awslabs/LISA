from typing import Annotated

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

    async def execute(self):
        return self.calculate
    
    async def calculate(
        self,
        operator: Annotated[str, "add, subtract, multiply, or divide"],
        left_operand: Annotated[float, "The first number"],
        right_operand: Annotated[float, "The second number"]
    ):
        """Execute the calculator operation."""        
        if operator == "add":
            result = left_operand + right_operand
        elif operator == "subtract":
            result = left_operand - right_operand
        elif operator == "multiply":
            result = left_operand * right_operand
        elif operator == "divide":
            if right_operand == 0:
                raise ValueError("Cannot divide by zero")
            result = left_operand / right_operand
        else:
            raise ValueError(f"Unknown operator: {operator}")
        
        return {
            "operator": operator,
            "left_operand": left_operand,
            "right_operand": right_operand,
            "result": result
        }
