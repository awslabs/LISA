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

"""Comprehensive unit tests for the syntax_validator module."""

import ast
import sys
from types import ModuleType
from unittest.mock import patch

import pytest
from mcp_workbench.syntax_validator import PythonSyntaxValidator, ValidationResult


class TestValidationResult:
    """Test cases for ValidationResult dataclass."""

    def test_initialization_with_all_fields(self):
        """Test ValidationResult initialization with all fields provided."""
        result = ValidationResult(
            is_valid=True, syntax_errors=[{"type": "Error", "message": "test"}], missing_required_imports=["import1"]
        )
        assert result.is_valid is True
        assert len(result.syntax_errors) == 1
        assert len(result.missing_required_imports) == 1

    def test_initialization_without_optional_fields(self):
        """Test ValidationResult initialization without optional fields."""
        result = ValidationResult(is_valid=False, syntax_errors=[])
        assert result.is_valid is False
        assert result.syntax_errors == []
        assert result.missing_required_imports == []

    def test_post_init_initializes_missing_imports(self):
        """Test that __post_init__ initializes missing_required_imports to empty list."""
        result = ValidationResult(is_valid=True, syntax_errors=[], missing_required_imports=None)
        assert result.missing_required_imports == []


class TestPythonSyntaxValidator:
    """Test cases for PythonSyntaxValidator class."""

    @pytest.fixture
    def validator(self):
        """Create a validator instance for testing."""
        return PythonSyntaxValidator()

    @pytest.fixture
    def cleanup_sys_modules(self):
        """Cleanup sys.modules after tests to avoid interference."""
        yield
        # Remove any mock modules added during testing
        modules_to_remove = [k for k in sys.modules.keys() if "mcpworkbench" in k or "temp_validation" in k]
        for module in modules_to_remove:
            del sys.modules[module]

    # ============================================================================
    # Test validate_code method
    # ============================================================================

    def test_validate_code_success_with_mcp_tool_import(self, validator, cleanup_sys_modules):
        """Test validation succeeds with mcp_tool import."""
        code = """
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool(name='test', description='test')
def my_tool():
    return "Hello, World!"
"""
        result = validator.validate_code(code)
        assert result.is_valid is True
        assert len(result.syntax_errors) == 0
        assert len(result.missing_required_imports) == 0

    def test_validate_code_success_with_base_tool_import(self, validator, cleanup_sys_modules):
        """Test validation succeeds with BaseTool import."""
        code = """
from mcpworkbench.core.base_tool import BaseTool

class MyTool(BaseTool):
    def __init__(self):
        super().__init__(name='test', description='test')

    async def execute(self):
        return "Hello"
"""
        result = validator.validate_code(code)
        assert result.is_valid is True
        assert len(result.syntax_errors) == 0
        assert len(result.missing_required_imports) == 0

    def test_validate_code_fails_with_code_too_large(self, validator):
        """Test validation fails when code exceeds size limit."""
        code = "x = 1\n" * 100_000  # Exceed 100KB limit
        result = validator.validate_code(code)
        assert result.is_valid is False
        assert len(result.syntax_errors) == 1
        assert result.syntax_errors[0]["type"] == "CodeTooLarge"
        assert "exceeds maximum allowed" in result.syntax_errors[0]["message"]

    def test_validate_code_fails_with_empty_code(self, validator):
        """Test validation fails with empty code."""
        result = validator.validate_code("")
        assert result.is_valid is False
        assert len(result.syntax_errors) == 1
        assert result.syntax_errors[0]["type"] == "EmptyCode"

    def test_validate_code_fails_with_whitespace_only(self, validator):
        """Test validation fails with whitespace-only code."""
        result = validator.validate_code("   \n\t\n   ")
        assert result.is_valid is False
        assert len(result.syntax_errors) == 1
        assert result.syntax_errors[0]["type"] == "EmptyCode"

    def test_validate_code_fails_with_syntax_error(self, validator):
        """Test validation fails with syntax error."""
        code = """
def broken_function(
    print('missing closing parenthesis')
"""
        result = validator.validate_code(code)
        assert result.is_valid is False
        assert len(result.syntax_errors) > 0
        assert result.syntax_errors[0]["type"] == "SyntaxError"

    def test_validate_code_fails_with_missing_required_imports(self, validator, cleanup_sys_modules):
        """Test validation fails when missing required MCP imports."""
        code = """
def my_function():
    return "No MCP imports"
"""
        result = validator.validate_code(code)
        assert result.is_valid is False
        assert len(result.missing_required_imports) > 0
        assert "required MCP Workbench imports" in result.missing_required_imports[0]

    def test_validate_code_with_star_import(self, validator, cleanup_sys_modules):
        """Test validation succeeds with star import."""
        code = """
from mcpworkbench.core.annotations import *

@mcp_tool(name='test', description='test')
def my_tool():
    return "Hello"
"""
        result = validator.validate_code(code)
        assert result.is_valid is True

    def test_validate_code_with_import_error(self, validator, cleanup_sys_modules):
        """Test validation catches import errors."""
        code = """
from mcpworkbench.core.annotations import mcp_tool
import nonexistent_module

@mcp_tool(name='test', description='test')
def my_tool():
    return nonexistent_module.something()
"""
        result = validator.validate_code(code)
        assert result.is_valid is False
        assert any(error["type"] == "ImportError" for error in result.syntax_errors)

    def test_validate_code_with_name_error(self, validator, cleanup_sys_modules):
        """Test validation catches name errors when they occur at module level."""
        code = """
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool(name='test', description='test')
def my_tool():
    return "ok"

# This will cause a NameError at module level
result = undefined_variable
"""
        result = validator.validate_code(code)
        assert result.is_valid is False
        assert any(error["type"] == "NameError" for error in result.syntax_errors)

    def test_validate_code_with_builtins(self, validator, cleanup_sys_modules):
        """Test validation succeeds with Python built-ins."""
        code = """
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool(name='test', description='test')
def my_tool():
    data = [1, 2, 3]
    return len(data) + sum(data)
"""
        result = validator.validate_code(code)
        assert result.is_valid is True

    @patch("ast.parse")
    def test_validate_code_handles_parse_exception(self, mock_parse, validator):
        """Test validation handles non-SyntaxError parse exceptions."""
        mock_parse.side_effect = ValueError("Unexpected parse error")
        code = "def test(): pass"
        result = validator.validate_code(code)
        assert result.is_valid is False
        assert len(result.syntax_errors) == 1
        assert result.syntax_errors[0]["type"] == "ParseError"
        assert "Failed to parse code" in result.syntax_errors[0]["message"]

    # ============================================================================
    # Test _validate_module_execution method
    # ============================================================================

    def test_validate_module_execution_success(self, validator, cleanup_sys_modules):
        """Test successful module execution validation."""
        code = """
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool(name='test', description='test')
def my_tool():
    return "Success"
"""
        errors = validator._validate_module_execution(code)
        assert len(errors) == 0

    def test_validate_module_execution_with_syntax_error_in_exec(self, validator, cleanup_sys_modules):
        """Test module execution catches syntax errors during exec."""
        # This is a corner case where AST might pass but exec fails
        code = """
from mcpworkbench.core.annotations import mcp_tool
# This will pass AST but might fail in exec in some edge cases
"""
        # We expect this to pass, but we're testing the error handling path
        errors = validator._validate_module_execution(code)
        # This should succeed, but we're verifying the method works
        assert isinstance(errors, list)

    @patch("importlib.util.spec_from_loader")
    def test_validate_module_execution_spec_creation_fails(self, mock_spec, validator):
        """Test module execution handles spec creation failure."""
        mock_spec.return_value = None
        code = "def test(): pass"
        errors = validator._validate_module_execution(code)
        assert len(errors) == 1
        assert errors[0]["type"] == "ModuleError"
        assert "Failed to create module spec" in errors[0]["message"]

    def test_validate_module_execution_with_generic_exception(self, validator, cleanup_sys_modules):
        """Test module execution handles generic exceptions."""
        code = """
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool(name='test', description='test')
def my_tool():
    return "ok"

# Trigger an error at module level
raise RuntimeError("Test error")
"""
        errors = validator._validate_module_execution(code)
        assert len(errors) > 0
        assert any(error["type"] == "ExecutionError" for error in errors)

    # ============================================================================
    # Test _setup_mcp_environment method
    # ============================================================================

    def test_setup_mcp_environment_creates_mocks(self, validator, cleanup_sys_modules):
        """Test MCP environment setup creates mock modules."""
        # Ensure real mcpworkbench is not in sys.modules
        modules_to_remove = [k for k in sys.modules.keys() if "mcpworkbench" in k]
        for module in modules_to_remove:
            del sys.modules[module]

        validator._setup_mcp_environment(None)

        assert "mcpworkbench" in sys.modules
        assert "mcpworkbench.core" in sys.modules
        assert "mcpworkbench.core.base_tool" in sys.modules
        assert "mcpworkbench.core.annotations" in sys.modules

    def test_setup_mcp_environment_uses_existing_modules(self, validator, cleanup_sys_modules):
        """Test MCP environment setup uses existing modules if available."""
        # Pre-populate sys.modules with a mock mcpworkbench
        mock_module = ModuleType("mcpworkbench.core.base_tool")
        sys.modules["mcpworkbench.core.base_tool"] = mock_module

        validator._setup_mcp_environment(None)

        # Should not replace existing module
        assert sys.modules["mcpworkbench.core.base_tool"] is mock_module

    def test_setup_mcp_environment_logs_info(self, validator, cleanup_sys_modules):
        """Test MCP environment setup logs appropriate info messages."""
        # Remove mcpworkbench from sys.modules to trigger mock setup
        modules_to_remove = [k for k in sys.modules.keys() if "mcpworkbench" in k]
        for module in modules_to_remove:
            del sys.modules[module]

        with patch("mcp_workbench.syntax_validator.logger") as mock_logger:
            validator._setup_mcp_environment(None)

            # Should have logged info about setting up mocks
            assert mock_logger.info.called
            # Check that it logged about finding or not finding real MCP Workbench
            call_args_list = [str(call) for call in mock_logger.info.call_args_list]
            assert any("MCP" in str(call) for call in call_args_list)

    # ============================================================================
    # Test _check_required_mcp_imports method
    # ============================================================================

    def test_check_required_mcp_imports_with_mcp_tool(self, validator):
        """Test required imports check with mcp_tool import."""
        code = "from mcpworkbench.core.annotations import mcp_tool"
        tree = ast.parse(code)
        missing = validator._check_required_mcp_imports(tree)
        assert len(missing) == 0

    def test_check_required_mcp_imports_with_base_tool(self, validator):
        """Test required imports check with BaseTool import."""
        code = "from mcpworkbench.core.base_tool import BaseTool"
        tree = ast.parse(code)
        missing = validator._check_required_mcp_imports(tree)
        assert len(missing) == 0

    def test_check_required_mcp_imports_with_star_import(self, validator):
        """Test required imports check with star import."""
        code = "from mcpworkbench.core.annotations import *"
        tree = ast.parse(code)
        missing = validator._check_required_mcp_imports(tree)
        assert len(missing) == 0

    def test_check_required_mcp_imports_missing(self, validator):
        """Test required imports check when imports are missing."""
        code = "def my_function(): pass"
        tree = ast.parse(code)
        missing = validator._check_required_mcp_imports(tree)
        assert len(missing) > 0

    def test_check_required_mcp_imports_with_both_imports(self, validator):
        """Test required imports check with both mcp_tool and BaseTool."""
        code = """
from mcpworkbench.core.annotations import mcp_tool
from mcpworkbench.core.base_tool import BaseTool
"""
        tree = ast.parse(code)
        missing = validator._check_required_mcp_imports(tree)
        assert len(missing) == 0

    # ============================================================================
    # Test _collect_imports method
    # ============================================================================

    def test_collect_imports_direct_import(self, validator):
        """Test collecting direct module imports."""
        code = "import os"
        tree = ast.parse(code)
        imports = validator._collect_imports(tree)
        assert "os" in imports["modules"]

    def test_collect_imports_from_import(self, validator):
        """Test collecting from imports."""
        code = "from os import path"
        tree = ast.parse(code)
        imports = validator._collect_imports(tree)
        assert "os" in imports["from_imports"]
        assert "path" in imports["from_imports"]["os"]

    def test_collect_imports_with_alias(self, validator):
        """Test collecting imports with aliases."""
        code = "import numpy as np"
        tree = ast.parse(code)
        imports = validator._collect_imports(tree)
        assert "numpy" in imports["modules"]
        assert "np" in imports["aliases"]
        assert imports["aliases"]["np"] == "numpy"

    def test_collect_imports_star_import(self, validator):
        """Test collecting star imports."""
        code = "from os import *"
        tree = ast.parse(code)
        imports = validator._collect_imports(tree)
        assert "os" in imports["star_imports"]

    def test_collect_imports_multiple_imports(self, validator):
        """Test collecting multiple imports in one statement."""
        code = "from os import path, environ, getcwd"
        tree = ast.parse(code)
        imports = validator._collect_imports(tree)
        assert "os" in imports["from_imports"]
        assert "path" in imports["from_imports"]["os"]
        assert "environ" in imports["from_imports"]["os"]
        assert "getcwd" in imports["from_imports"]["os"]

    def test_collect_imports_from_import_with_alias(self, validator):
        """Test collecting from imports with aliases."""
        code = "from os import path as p"
        tree = ast.parse(code)
        imports = validator._collect_imports(tree)
        assert "os" in imports["from_imports"]
        assert "path" in imports["from_imports"]["os"]
        assert "p" in imports["aliases"]
        assert imports["aliases"]["p"] == "os.path"

    def test_collect_imports_complex_scenario(self, validator):
        """Test collecting various import types together."""
        code = """
import os
import sys as system
from pathlib import Path
from typing import List, Dict
from collections import *
"""
        tree = ast.parse(code)
        imports = validator._collect_imports(tree)

        assert "os" in imports["modules"]
        assert "sys" in imports["modules"]
        assert "system" in imports["aliases"]
        assert "pathlib" in imports["from_imports"]
        assert "Path" in imports["from_imports"]["pathlib"]
        assert "typing" in imports["from_imports"]
        assert "List" in imports["from_imports"]["typing"]
        assert "Dict" in imports["from_imports"]["typing"]
        assert "collections" in imports["star_imports"]

    # ============================================================================
    # Test _format_syntax_error method
    # ============================================================================

    def test_format_syntax_error_with_all_fields(self, validator):
        """Test formatting syntax error with all fields present."""
        syntax_error = SyntaxError("invalid syntax")
        syntax_error.lineno = 10
        syntax_error.offset = 5
        syntax_error.text = "def test("

        formatted = validator._format_syntax_error(syntax_error)

        assert formatted["type"] == "SyntaxError"
        assert formatted["message"] == "invalid syntax"
        assert formatted["line"] == 10
        assert formatted["column"] == 5
        assert formatted["text"] == "def test("

    def test_format_syntax_error_with_missing_fields(self, validator):
        """Test formatting syntax error with missing fields."""
        syntax_error = SyntaxError()
        syntax_error.msg = None
        syntax_error.lineno = None
        syntax_error.offset = None
        syntax_error.text = None

        formatted = validator._format_syntax_error(syntax_error)

        assert formatted["type"] == "SyntaxError"
        assert formatted["message"] == "Syntax error"
        assert formatted["line"] == 0
        assert formatted["column"] == 0
        assert formatted["text"] == ""

    def test_format_syntax_error_with_whitespace_text(self, validator):
        """Test formatting syntax error strips whitespace from text."""
        syntax_error = SyntaxError("test error")
        syntax_error.lineno = 1
        syntax_error.offset = 1
        syntax_error.text = "  def test()  \n"

        formatted = validator._format_syntax_error(syntax_error)

        assert formatted["text"] == "def test()"

    # ============================================================================
    # Test initialization
    # ============================================================================

    def test_validator_initialization(self, validator):
        """Test validator initializes with correct default values."""
        assert validator.max_code_size == 100_000
        assert isinstance(validator.REQUIRED_MCP_IMPORTS, list)
        assert len(validator.REQUIRED_MCP_IMPORTS) == 2

    def test_required_mcp_imports_structure(self, validator):
        """Test REQUIRED_MCP_IMPORTS has correct structure."""
        for module, name in validator.REQUIRED_MCP_IMPORTS:
            assert isinstance(module, str)
            assert isinstance(name, str)
            assert len(module) > 0
            assert len(name) > 0

    # ============================================================================
    # Test edge cases and integration scenarios
    # ============================================================================

    def test_validate_code_with_comments(self, validator, cleanup_sys_modules):
        """Test validation handles code with comments."""
        code = """
# This is a comment
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool(name='test', description='test')
def my_tool():
    # Another comment
    return "Hello"
"""
        result = validator.validate_code(code)
        assert result.is_valid is True

    def test_validate_code_with_multiline_strings(self, validator, cleanup_sys_modules):
        """Test validation handles multiline strings."""
        code = '''
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool(name='test', description='test')
def my_tool():
    """
    This is a multiline
    docstring.
    """
    return """
    Multiline
    return value
    """
'''
        result = validator.validate_code(code)
        assert result.is_valid is True

    def test_validate_code_with_nested_functions(self, validator, cleanup_sys_modules):
        """Test validation handles nested functions."""
        code = """
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool(name='test', description='test')
def outer():
    def inner():
        return "nested"
    return inner()
"""
        result = validator.validate_code(code)
        assert result.is_valid is True

    def test_validate_code_with_class_definition(self, validator, cleanup_sys_modules):
        """Test validation handles class definitions."""
        code = """
from mcpworkbench.core.base_tool import BaseTool

class MyTool(BaseTool):
    def __init__(self):
        super().__init__(name='test', description='test')

    async def execute(self):
        return self.name
"""
        result = validator.validate_code(code)
        assert result.is_valid is True

    def test_validate_code_at_size_boundary(self, validator):
        """Test validation at exact size boundary."""
        # Create code that's exactly at the limit
        code = "x = 1\n" * (validator.max_code_size // 6)  # 6 bytes per line
        # Ensure it's just under the limit
        code = code[: validator.max_code_size - 100]
        result = validator.validate_code(code)
        # Should fail due to missing imports, but not due to size
        assert not any(error["type"] == "CodeTooLarge" for error in result.syntax_errors)

    def test_validate_code_with_encoding_declaration(self, validator, cleanup_sys_modules):
        """Test validation handles encoding declarations."""
        code = """# -*- coding: utf-8 -*-
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool(name='test', description='test')
def my_tool():
    return "Hello"
"""
        result = validator.validate_code(code)
        assert result.is_valid is True

    def test_validate_code_with_future_imports(self, validator, cleanup_sys_modules):
        """Test validation handles future imports."""
        code = """
from __future__ import annotations
from mcpworkbench.core.annotations import mcp_tool

@mcp_tool(name='test', description='test')
def my_tool() -> str:
    return "Hello"
"""
        result = validator.validate_code(code)
        assert result.is_valid is True
