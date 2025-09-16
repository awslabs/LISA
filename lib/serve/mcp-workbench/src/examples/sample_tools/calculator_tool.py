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

"""
MCP Tool Creation Tutorial
==========================

This file demonstrates how to create MCP (Model Context Protocol) tools using two different approaches:
1. Class-based method (shown in this file)
2. Function-based method with @mcp_tool decorator (shown in comments below)

Both methods allow you to create tools that can be called by AI models to perform specific tasks.
"""

from typing import Annotated

from mcpworkbench.core.base_tool import BaseTool

# =============================================================================
# METHOD 1: CLASS-BASED APPROACH
# =============================================================================
# This is the more structured approach, ideal for complex tools that need
# initialization, state management, or multiple related operations.


class CalculatorTool(BaseTool):
    """
    A simple calculator tool that performs basic arithmetic operations.

    This class demonstrates the class-based approach to creating MCP tools:
    1. Inherit from BaseTool
    2. Initialize with name and description in __init__
    3. Implement execute() method that returns the callable function
    4. Define the actual tool function with proper type annotations
    """

    def __init__(self):
        """
        Initialize the tool with metadata.

        The BaseTool constructor requires:
        - name: A unique identifier for the tool
        - description: A clear description of what the tool does
        """
        super().__init__(
            name="calculator", description="Performs basic arithmetic operations (add, subtract, multiply, divide)"
        )

    async def execute(self):
        """
        Return the callable function that implements the tool's functionality.

        This method is called by the MCP framework to get the actual function
        that will be executed when the tool is invoked.
        """
        return self.calculate

    async def calculate(
        self,
        operator: Annotated[str, "add, subtract, multiply, or divide"],
        left_operand: Annotated[float, "The first number"],
        right_operand: Annotated[float, "The second number"],
    ):
        """
        Execute the calculator operation.

        Parameter Type Annotations with Context:
        =======================================
        Notice the use of Annotated[type, "description"] for each parameter.
        This is OPTIONAL but highly recommended because it provides:

        1. Type information for the MCP framework
        2. Human-readable descriptions that help AI models understand
           what each parameter is for
        3. Better error messages and validation

        The Annotated type comes from typing module and follows this pattern:
        Annotated[actual_type, "description_string"]

        Examples:
        - Annotated[str, "The operation to perform"]
        - Annotated[int, "A positive integer between 1 and 100"]
        - Annotated[list[str], "A list of file paths to process"]
        """
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

        return {"operator": operator, "left_operand": left_operand, "right_operand": right_operand, "result": result}


# =============================================================================
# METHOD 2: FUNCTION-BASED APPROACH WITH @mcp_tool DECORATOR
# =============================================================================
# This is a simpler approach for straightforward tools that don't need
# complex initialization or state management.

"""
Here's how you would implement the same calculator using the @mcp_tool decorator:

from mcpworkbench.core.decorators import mcp_tool
from typing import Annotated

@mcp_tool(
    name="simple_calculator",
    description="A simple calculator using the decorator approach"
)
async def simple_calculator(
    operator: Annotated[str, "The arithmetic operation: add, subtract, multiply, or divide"],
    left_operand: Annotated[float, "The first number in the operation"],
    right_operand: Annotated[float, "The second number in the operation"]
) -> dict:
    '''
    Perform basic arithmetic operations using the decorator approach.

    The @mcp_tool decorator automatically:
    1. Registers the function as an MCP tool
    2. Extracts parameter information from type annotations
    3. Uses the Annotated descriptions for parameter documentation
    4. Handles the MCP protocol communication

    This approach is ideal for:
    - Simple, stateless operations
    - Quick prototyping
    - Tools that don't need complex initialization
    '''

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

# Additional examples of Annotated usage for different parameter types:

@mcp_tool(name="file_processor", description="Process files with various options")
async def process_files(
    file_paths: Annotated[list[str], "List of file paths to process"],
    max_size: Annotated[int, "Maximum file size in bytes (default: 1MB)"] = 1024*1024,
    format: Annotated[str, "Output format: 'json', 'csv', or 'txt'"] = "json",
    recursive: Annotated[bool, "Whether to process subdirectories recursively"] = False
):
    '''
    Example showing different parameter types with Annotated descriptions.

    Key points about Annotated:
    - Works with any Python type: str, int, float, bool, list, dict, etc.
    - The description should be clear and specific
    - Can include examples, constraints, or default behavior
    - Helps AI models understand how to use your tool correctly
    '''
    pass
"""

# =============================================================================
# CHOOSING BETWEEN THE TWO APPROACHES
# =============================================================================
"""
When to use Class-based approach:
- Complex tools with multiple related functions
- Tools that need initialization or configuration
- Tools that maintain state between calls
- Tools that need to share resources or connections
- When you want to group related functionality together

When to use @mcp_tool decorator:
- Simple, stateless operations
- Quick prototyping and testing
- Single-purpose tools
- When you want minimal boilerplate code
- For functional programming style

Both approaches support:
- Async/await operations
- Type annotations with Annotated for parameter descriptions
- Error handling and validation
- Return value serialization
- Integration with the MCP protocol
"""
