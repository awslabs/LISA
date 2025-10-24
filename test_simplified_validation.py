#!/usr/bin/env python3

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

import os
import sys

from mcp_workbench.syntax_validator import PythonSyntaxValidator

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lambda"))


def test_simplified_validator():
    """Test the simplified syntax validator."""
    validator = PythonSyntaxValidator()

    # Test 1: Valid code with required imports
    valid_code = """
from mcpworkbench.core.annotations import mcp_tool
from mcpworkbench.core.base_tool import BaseTool

@mcp_tool(name='test_tool', description='A test tool')
def test_function():
    return 'Hello World'

class TestTool(BaseTool):
    def __init__(self):
        super().__init__(name='test', description='Test tool')
"""

    print("=== Test 1: Valid code with required imports ===")
    result = validator.validate_code(valid_code)
    print(f"Valid: {result.is_valid}")
    print(f"Syntax errors: {len(result.syntax_errors)}")
    print(f"Missing imports: {len(result.missing_required_imports)}")
    if result.syntax_errors:
        for error in result.syntax_errors:
            print(f'  Error: {error["type"]} - {error["message"]}')

    # Test 2: Syntax error
    syntax_error_code = """
def broken_function(
    print('missing closing parenthesis')
"""

    print("\n=== Test 2: Syntax error ===")
    result = validator.validate_code(syntax_error_code)
    print(f"Valid: {result.is_valid}")
    print(f"Syntax errors: {len(result.syntax_errors)}")
    if result.syntax_errors:
        print(f'Error type: {result.syntax_errors[0]["type"]}')
        print(f'Error message: {result.syntax_errors[0]["message"]}')

    # Test 3: Missing required imports
    missing_imports_code = """
def some_function():
    return 'No MCP imports here'
"""

    print("\n=== Test 3: Missing required imports ===")
    result = validator.validate_code(missing_imports_code)
    print(f"Valid: {result.is_valid}")
    print(f"Syntax errors: {len(result.syntax_errors)}")
    print(f"Missing imports: {len(result.missing_required_imports)}")
    if result.missing_required_imports:
        print(f"Missing import message: {result.missing_required_imports[0]}")

    # Test 4: Import error (undefined module)
    import_error_code = """
from mcpworkbench.core.annotations import mcp_tool
import nonexistent_module

def test_function():
    return nonexistent_module.something()
"""

    print("\n=== Test 4: Import error ===")
    result = validator.validate_code(import_error_code)
    print(f"Valid: {result.is_valid}")
    print(f"Syntax errors: {len(result.syntax_errors)}")
    if result.syntax_errors:
        for error in result.syntax_errors:
            print(f'  Error: {error["type"]} - {error["message"]}')

    print("\n=== All tests completed ===")


if __name__ == "__main__":
    test_simplified_validator()
