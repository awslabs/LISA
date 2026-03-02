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

"""Python syntax validation module for MCP Workbench."""
import ast
import importlib.util
import logging
import os
import sys
from dataclasses import dataclass
from types import ModuleType
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of Python code validation."""

    is_valid: bool
    syntax_errors: list[dict[str, Any]]
    missing_required_imports: list[str] | None = None

    def __post_init__(self) -> None:
        """Initialize list fields if None."""
        if self.missing_required_imports is None:
            self.missing_required_imports = []


class PythonSyntaxValidator:
    """Validates Python code syntax and imports without execution."""

    # Required MCP Workbench imports
    REQUIRED_MCP_IMPORTS = [("mcpworkbench.core.annotations", "mcp_tool"), ("mcpworkbench.core.base_tool", "BaseTool")]

    def __init__(self) -> None:
        """Initialize the validator."""
        # Safety limits
        self.max_code_size = 100_000  # 100KB

    def validate_code(self, code: str) -> ValidationResult:
        """
        Validate Python code for syntax and required imports.

        Args:
            code: Python code string to validate

        Returns:
            ValidationResult with validation details
        """
        syntax_errors = []

        # Safety checks
        if len(code) > self.max_code_size:
            return ValidationResult(
                is_valid=False,
                syntax_errors=[
                    {
                        "type": "CodeTooLarge",
                        "message": (
                            f"Code size ({len(code)} bytes) exceeds maximum allowed ({self.max_code_size} bytes)"
                        ),
                        "line": 0,
                        "column": 0,
                    }
                ],
                missing_required_imports=[],
            )

        # Basic input validation
        if not code or not code.strip():
            return ValidationResult(
                is_valid=False,
                syntax_errors=[{"type": "EmptyCode", "message": "Code cannot be empty", "line": 0, "column": 0}],
                missing_required_imports=[],
            )

        # 1. AST-based syntax validation (fast check)
        try:
            tree = ast.parse(code)
            logger.info("AST parsing successful")
        except SyntaxError as e:
            syntax_errors.append(self._format_syntax_error(e))
            logger.warning(f"Syntax error: {e}")

            # Return early if syntax is invalid
            return ValidationResult(is_valid=False, syntax_errors=syntax_errors, missing_required_imports=[])
        except Exception as e:
            syntax_errors.append(
                {"type": "ParseError", "message": f"Failed to parse code: {str(e)}", "line": 0, "column": 0}
            )
            logger.error(f"Parse error: {e}")
            return ValidationResult(is_valid=False, syntax_errors=syntax_errors, missing_required_imports=[])

        # 2. Module execution validation (comprehensive check)
        execution_errors = self._validate_module_execution(code)
        syntax_errors.extend(execution_errors)

        # 3. Check for required MCP imports
        missing_required_imports = self._check_required_mcp_imports(tree)

        # Determine overall validity
        is_valid = len(syntax_errors) == 0 and len(missing_required_imports) == 0

        return ValidationResult(
            is_valid=is_valid, syntax_errors=syntax_errors, missing_required_imports=missing_required_imports
        )

    def _validate_module_execution(self, code: str) -> list[dict[str, Any]]:
        """Validate code by attempting to execute it as a module."""
        errors = []

        try:
            # Set up the MCP environment FIRST (inject mocks into sys.modules)
            # This must happen before exec() so imports can find the mocks
            self._setup_mcp_environment(None)

            # Create a temporary module spec
            spec = importlib.util.spec_from_loader("temp_validation_module", loader=None)
            if spec is None:
                errors.append(
                    {
                        "type": "ModuleError",
                        "message": "Failed to create module spec for validation",
                        "line": 0,
                        "column": 0,
                    }
                )
                return errors

            module = importlib.util.module_from_spec(spec)

            # Execute the code in the module context
            # The mocks are already in sys.modules so imports will work
            exec(code, module.__dict__)  # nosec B102
            logger.info("Module execution successful")

        except ImportError as e:
            errors.append({"type": "ImportError", "message": str(e), "line": 0, "column": 0})
            logger.warning(f"Import error during execution: {e}")
        except SyntaxError as e:
            # Shouldn't happen since AST passed, but just in case
            errors.append(self._format_syntax_error(e))
            logger.warning(f"Syntax error during execution: {e}")
        except NameError as e:
            errors.append({"type": "NameError", "message": str(e), "line": 0, "column": 0})
            logger.warning(f"Name error during execution: {e}")
        except Exception as e:
            errors.append(
                {"type": "ExecutionError", "message": f"Error executing code: {str(e)}", "line": 0, "column": 0}
            )
            logger.error(f"Execution error: {e}")

        return errors

    def _setup_mcp_environment(self, module: Any) -> None:
        """Set up the module with required MCP imports available."""
        # Check if real MCP Workbench is available
        if "mcpworkbench.core.base_tool" not in sys.modules:
            # Real package not available, inject mocks into sys.modules
            logger.info("Real MCP Workbench not found, setting up mocks")
            mcp_tool_func: Any = None
            base_tool_class: Any = None

            try:
                # Try relative import first (when running as part of a package)
                from .mcp_mocks import BaseTool as base_tool_class  # noqa: PLC0415
                from .mcp_mocks import mcp_tool as mcp_tool_func  # noqa: PLC0415

                logger.info("Successfully imported mocks via relative import")
            except ImportError as e:
                logger.info(f"Relative import failed: {e}, trying absolute import")
                try:
                    # Fall back to absolute import (when running standalone)
                    import mcp_mocks  # noqa: PLC0415

                    mcp_tool_func = mcp_mocks.mcp_tool
                    base_tool_class = mcp_mocks.BaseTool
                    logger.info("Successfully imported mocks via absolute import")
                except ImportError as mock_error:
                    logger.error(f"CRITICAL: Failed to import MCP mocks via both methods: {mock_error}")
                    logger.error(f"Current directory: {os.getcwd() if 'os' in dir() else 'unknown'}")
                    logger.error(f"sys.path: {sys.path[:3]}")  # Show first 3 paths
                    return

            # Create mock module hierarchy in sys.modules
            # This allows user code to do: from mcpworkbench.core.base_tool import BaseTool
            if "mcpworkbench" not in sys.modules:
                sys.modules["mcpworkbench"] = ModuleType("mcpworkbench")

            if "mcpworkbench.core" not in sys.modules:
                core_module = ModuleType("mcpworkbench.core")
                sys.modules["mcpworkbench.core"] = core_module
                sys.modules["mcpworkbench"].core = core_module  # type: ignore[attr-defined]

            # Create and register the base_tool mock module
            base_tool_module = ModuleType("mcpworkbench.core.base_tool")
            base_tool_module.BaseTool = base_tool_class  # type: ignore[attr-defined]
            sys.modules["mcpworkbench.core.base_tool"] = base_tool_module
            sys.modules["mcpworkbench.core"].base_tool = base_tool_module  # type: ignore[attr-defined]

            # Create and register the annotations mock module
            annotations_module = ModuleType("mcpworkbench.core.annotations")
            annotations_module.mcp_tool = mcp_tool_func  # type: ignore[attr-defined]
            sys.modules["mcpworkbench.core.annotations"] = annotations_module
            sys.modules["mcpworkbench.core"].annotations = annotations_module  # type: ignore[attr-defined]

            logger.info("MCP mock modules successfully injected into sys.modules")
            logger.info(f"Modules now in sys.modules: {[k for k in sys.modules.keys() if 'mcpworkbench' in k]}")
        else:
            logger.info("Real MCP Workbench package is already available in sys.modules")

    def _check_required_mcp_imports(self, tree: ast.AST) -> list[str]:
        """Check if required MCP imports are present in the AST."""
        missing_required = []

        # Collect all imports from the AST
        imports = self._collect_imports(tree)

        # Check if at least one required import is present
        has_required_import = False

        for module, name in self.REQUIRED_MCP_IMPORTS:
            # Check if imported via 'from module import name'
            if module in imports["from_imports"] and name in imports["from_imports"][module]:
                has_required_import = True
                break

            # Check if imported via star import
            if module in imports["star_imports"]:
                has_required_import = True
                break

        if not has_required_import:
            missing_required.append("At least one of the required MCP Workbench imports is missing")

        return missing_required

    def _collect_imports(self, tree: ast.AST) -> dict[str, Any]:
        """Collect all import statements from the AST."""
        imports: dict[str, Any] = {
            "modules": set(),  # Direct module imports: import os
            "from_imports": {},  # From imports: from os import path -> {'os': {'path'}}
            "aliases": {},  # Import aliases: import numpy as np -> {'np': 'numpy'}
            "star_imports": set(),  # Star imports: from os import *
        }

        class ImportVisitor(ast.NodeVisitor):
            def visit_Import(self, node: ast.Import) -> None:
                for alias in node.names:
                    module_name = alias.name
                    alias_name = alias.asname or module_name
                    imports["modules"].add(module_name)
                    if alias.asname:
                        imports["aliases"][alias_name] = module_name
                self.generic_visit(node)

            def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
                if node.module:
                    module_name = node.module
                    if node.names and len(node.names) == 1 and node.names[0].name == "*":
                        # Star import
                        imports["star_imports"].add(module_name)
                    else:
                        # Regular from import
                        if module_name not in imports["from_imports"]:
                            imports["from_imports"][module_name] = set()

                        for alias in node.names:
                            name = alias.name
                            alias_name = alias.asname or name
                            imports["from_imports"][module_name].add(name)
                            if alias.asname:
                                imports["aliases"][alias_name] = f"{module_name}.{name}"
                self.generic_visit(node)

        visitor = ImportVisitor()
        visitor.visit(tree)
        return imports

    def _format_syntax_error(self, syntax_error: SyntaxError) -> dict[str, Any]:
        """Format a SyntaxError into a standardized error dictionary."""
        return {
            "type": "SyntaxError",
            "message": str(syntax_error.msg) if syntax_error.msg else "Syntax error",
            "line": syntax_error.lineno or 0,
            "column": syntax_error.offset or 0,
            "text": syntax_error.text.strip() if syntax_error.text else "",
        }
