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

"""Test script for the enhanced syntax validation with import checking."""

import os
import sys

from mcp_workbench.syntax_validator import PythonSyntaxValidator

# Add the lambda directory to the path so we can import the modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lambda"))


def test_validation():
    """Test the enhanced validation functionality."""
    validator = PythonSyntaxValidator()

    print("🧪 Testing Enhanced Python Syntax Validation")
    print("=" * 50)

    # Test cases
    test_cases = [
        {
            "name": "Valid MCP Tool with required import",
            "code": """
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool
def my_tool():
    \"\"\"A simple MCP tool.\"\"\"
    return "Hello, World!"
""",
            "should_be_valid": True,
        },
        {
            "name": "Valid MCP Tool with BaseTool import",
            "code": """
from mcpworkbench.core.base_tool import BaseTool

class MyTool(BaseTool):
    \"\"\"A tool that extends BaseTool.\"\"\"

    def execute(self):
        return "Hello from BaseTool!"
""",
            "should_be_valid": True,
        },
        {
            "name": "Missing required MCP imports",
            "code": """
def my_function():
    \"\"\"A function without MCP imports.\"\"\"
    return "This should fail validation"
""",
            "should_be_valid": False,
        },
        {
            "name": "Missing general imports",
            "code": """
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool
def my_tool():
    \"\"\"Uses requests without importing it.\"\"\"
    response = requests.get("https://api.example.com")
    return response.json()
""",
            "should_be_valid": False,
        },
        {
            "name": "Valid code with proper imports",
            "code": """
from mcpworkbench.core.annotations import mcp_tool
import requests
import json

@mcp_tool
def fetch_data():
    \"\"\"Fetches data from an API.\"\"\"
    response = requests.get("https://api.example.com")
    return json.loads(response.text)
""",
            "should_be_valid": True,
        },
        {
            "name": "Syntax error",
            "code": """
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool
def broken_function(
    \"\"\"Missing closing parenthesis.\"\"\"
    return "This has a syntax error"
""",
            "should_be_valid": False,
        },
        {
            "name": "Code with built-ins (should be valid)",
            "code": """
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool
def use_builtins():
    \"\"\"Uses Python built-ins.\"\"\"
    data = [1, 2, 3, 4, 5]
    return len(data) + sum(data)
""",
            "should_be_valid": True,
        },
    ]

    # Run tests
    passed = 0
    failed = 0

    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🔍 Test {i}: {test_case['name']}")
        print("-" * 40)

        try:
            result = validator.validate_code(test_case["code"])

            # Check if the result matches expectation
            if result.is_valid == test_case["should_be_valid"]:
                print(f"✅ PASSED - Valid: {result.is_valid}")
                passed += 1
            else:
                print(f"❌ FAILED - Expected: {test_case['should_be_valid']}, Got: {result.is_valid}")
                failed += 1

            # Print detailed results
            print(f"   Syntax Errors: {len(result.syntax_errors)}")
            print(f"   Missing Required Imports: {len(result.missing_required_imports)}")

            # Print specific issues if any
            if result.syntax_errors:
                print("   📋 Syntax Errors:")
                for error in result.syntax_errors:
                    print(f"      - {error['type']}: {error['message']}")

            if result.missing_required_imports:
                print("   📋 Missing Required Imports:")
                for missing in result.missing_required_imports:
                    print(f"      - {missing}")

        except Exception as e:
            print(f"❌ ERROR - Exception occurred: {e}")
            failed += 1

    # Summary
    print("\n" + "=" * 50)
    print(f"📊 Test Summary: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests passed!")
        return True
    else:
        print("⚠️  Some tests failed.")
        return False


if __name__ == "__main__":
    success = test_validation()
    sys.exit(0 if success else 1)
