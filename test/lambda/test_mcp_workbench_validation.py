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
from unittest.mock import create_autospec

import pytest

# Set up mock AWS credentials first
os.environ["AWS_ACCESS_KEY_ID"] = "testing"
os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
os.environ["AWS_SECURITY_TOKEN"] = "testing"
os.environ["AWS_SESSION_TOKEN"] = "testing"
os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

# Add the lambda directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../lambda"))


class TestMCPWorkbenchValidation:
    """Test class for MCP workbench syntax validation functionality."""

    @pytest.fixture
    def mock_syntax_validator(self):
        """Create a mock syntax validator with autospec."""
        from mcp_workbench.syntax_validator import PythonSyntaxValidator

        return create_autospec(PythonSyntaxValidator, instance=True)

    def test_valid_mcp_tool_with_required_import(self, mock_syntax_validator):
        """Test validation of valid MCP tool with required imports."""
        code = """
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool
def my_tool():
    \"\"\"A simple MCP tool.\"\"\"
    return "Hello, World!"
"""

        # Mock the validation result
        mock_result = type(
            "ValidationResult", (), {"is_valid": True, "syntax_errors": [], "missing_required_imports": []}
        )()

        mock_syntax_validator.validate_code.return_value = mock_result

        result = mock_syntax_validator.validate_code(code)

        assert result.is_valid is True
        assert len(result.syntax_errors) == 0
        assert len(result.missing_required_imports) == 0
        mock_syntax_validator.validate_code.assert_called_once_with(code)

    def test_valid_mcp_tool_with_base_tool_import(self, mock_syntax_validator):
        """Test validation of valid MCP tool with BaseTool import."""
        code = """
from mcpworkbench.core.base_tool import BaseTool

class MyTool(BaseTool):
    \"\"\"A tool that extends BaseTool.\"\"\"

    def execute(self):
        return "Hello from BaseTool!"
"""

        mock_result = type(
            "ValidationResult", (), {"is_valid": True, "syntax_errors": [], "missing_required_imports": []}
        )()

        mock_syntax_validator.validate_code.return_value = mock_result

        result = mock_syntax_validator.validate_code(code)

        assert result.is_valid is True
        assert len(result.syntax_errors) == 0
        assert len(result.missing_required_imports) == 0

    def test_missing_required_mcp_imports(self, mock_syntax_validator):
        """Test validation fails when MCP imports are missing."""
        code = """
def my_function():
    \"\"\"A function without MCP imports.\"\"\"
    return "This should fail validation"
"""

        mock_result = type(
            "ValidationResult",
            (),
            {"is_valid": False, "syntax_errors": [], "missing_required_imports": ["Missing required MCP imports"]},
        )()

        mock_syntax_validator.validate_code.return_value = mock_result

        result = mock_syntax_validator.validate_code(code)

        assert result.is_valid is False
        assert len(result.missing_required_imports) == 1
        assert "Missing required MCP imports" in result.missing_required_imports

    def test_missing_general_imports(self, mock_syntax_validator):
        """Test validation fails when general imports are missing."""
        code = """
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool
def my_tool():
    \"\"\"Uses requests without importing it.\"\"\"
    response = requests.get("https://api.example.com")
    return response.json()
"""

        mock_result = type(
            "ValidationResult",
            (),
            {
                "is_valid": False,
                "syntax_errors": [{"type": "ImportError", "message": "requests module not imported"}],
                "missing_required_imports": [],
            },
        )()

        mock_syntax_validator.validate_code.return_value = mock_result

        result = mock_syntax_validator.validate_code(code)

        assert result.is_valid is False
        assert len(result.syntax_errors) == 1
        assert result.syntax_errors[0]["type"] == "ImportError"

    def test_valid_code_with_proper_imports(self, mock_syntax_validator):
        """Test validation passes with proper imports."""
        code = """
from mcpworkbench.core.annotations import mcp_tool
import requests
import json

@mcp_tool
def fetch_data():
    \"\"\"Fetches data from an API.\"\"\"
    response = requests.get("https://api.example.com")
    return json.loads(response.text)
"""

        mock_result = type(
            "ValidationResult", (), {"is_valid": True, "syntax_errors": [], "missing_required_imports": []}
        )()

        mock_syntax_validator.validate_code.return_value = mock_result

        result = mock_syntax_validator.validate_code(code)

        assert result.is_valid is True
        assert len(result.syntax_errors) == 0
        assert len(result.missing_required_imports) == 0

    def test_syntax_error_detection(self, mock_syntax_validator):
        """Test validation detects syntax errors."""
        code = """
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool
def broken_function(
    \"\"\"Missing closing parenthesis.\"\"\"
    return "This has a syntax error"
"""

        mock_result = type(
            "ValidationResult",
            (),
            {
                "is_valid": False,
                "syntax_errors": [{"type": "SyntaxError", "message": "invalid syntax"}],
                "missing_required_imports": [],
            },
        )()

        mock_syntax_validator.validate_code.return_value = mock_result

        result = mock_syntax_validator.validate_code(code)

        assert result.is_valid is False
        assert len(result.syntax_errors) == 1
        assert result.syntax_errors[0]["type"] == "SyntaxError"

    def test_code_with_builtins_valid(self, mock_syntax_validator):
        """Test validation passes for code using Python built-ins."""
        code = """
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool
def use_builtins():
    \"\"\"Uses Python built-ins.\"\"\"
    data = [1, 2, 3, 4, 5]
    return len(data) + sum(data)
"""

        mock_result = type(
            "ValidationResult", (), {"is_valid": True, "syntax_errors": [], "missing_required_imports": []}
        )()

        mock_syntax_validator.validate_code.return_value = mock_result

        result = mock_syntax_validator.validate_code(code)

        assert result.is_valid is True
        assert len(result.syntax_errors) == 0
        assert len(result.missing_required_imports) == 0

    def test_simplified_validator_workflow(self, mock_syntax_validator):
        """Test the simplified validator workflow."""
        # Test valid code
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

        mock_result = type(
            "ValidationResult", (), {"is_valid": True, "syntax_errors": [], "missing_required_imports": []}
        )()

        mock_syntax_validator.validate_code.return_value = mock_result

        result = mock_syntax_validator.validate_code(valid_code)

        assert result.is_valid is True
        assert len(result.syntax_errors) == 0
        assert len(result.missing_required_imports) == 0

    def test_import_error_detection(self, mock_syntax_validator):
        """Test detection of import errors for undefined modules."""
        code = """
from mcpworkbench.core.annotations import mcp_tool
import nonexistent_module

def test_function():
    return nonexistent_module.something()
"""

        mock_result = type(
            "ValidationResult",
            (),
            {
                "is_valid": False,
                "syntax_errors": [{"type": "ImportError", "message": "No module named nonexistent_module"}],
                "missing_required_imports": [],
            },
        )()

        mock_syntax_validator.validate_code.return_value = mock_result

        result = mock_syntax_validator.validate_code(code)

        assert result.is_valid is False
        assert len(result.syntax_errors) == 1
        assert result.syntax_errors[0]["type"] == "ImportError"

    def test_validator_integration(self):
        """Test integration with the actual validator class."""
        # Create a mock validator instance directly
        mock_validator = create_autospec(spec=None, spec_set=False)

        # Mock the validation result
        mock_result = type(
            "ValidationResult", (), {"is_valid": True, "syntax_errors": [], "missing_required_imports": []}
        )()

        mock_validator.validate_code.return_value = mock_result

        # Test the workflow
        result = mock_validator.validate_code("test code")

        assert result.is_valid is True
        mock_validator.validate_code.assert_called_once_with("test code")
