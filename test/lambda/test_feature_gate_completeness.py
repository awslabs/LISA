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

import ast
from pathlib import Path

import pytest

# Gated handlers live under both lambda/ and lib/, so paths in REQUIRED_GATES
# are relative to the repo root.
REPO_ROOT = Path(__file__).resolve().parents[2]

# Canonical mapping: toggle_key -> list of (repo_relative_path, function_name).
REQUIRED_GATES: dict[str, list[tuple[str, str]]] = {
    "deleteSessionHistory": [
        ("lambda/handlers/session/lambda_functions.py", "delete_session"),
        ("lambda/handlers/session/lambda_functions.py", "delete_user_sessions"),
    ],
    "uploadRagDocs": [
        ("lambda/handlers/repository/lambda_functions.py", "presigned_url"),
        ("lambda/handlers/repository/lambda_functions.py", "ingest_documents"),
    ],
}


def _decorators_for_function(tree: ast.AST, func_name: str) -> list[str]:
    """Return the decorator names applied to ``func_name`` in a parsed module.

    Handles both bare decorators (``@require_admin``) and call decorators
    (``@require_feature("x")``), and both ``Name`` and dotted ``Attribute``
    forms (``@module.require_feature(...)``).
    """
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            names: list[str] = []
            for dec in node.decorator_list:
                target = dec.func if isinstance(dec, ast.Call) else dec
                if isinstance(target, ast.Name):
                    names.append(target.id)
                elif isinstance(target, ast.Attribute):
                    names.append(target.attr)
            return names
    return []


def _require_feature_keys_for_function(tree: ast.AST, func_name: str) -> list[str]:
    """Return the string literal argument of every ``@require_feature("key")``
    decorator on ``func_name``.

    Lets the audit assert the endpoint is gated for the CORRECT toggle, not just
    that some ``require_feature`` decorator is present (which would let a
    copy-pasted wrong key slip through).
    """
    keys: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            for dec in node.decorator_list:
                if not isinstance(dec, ast.Call):
                    continue
                target = dec.func
                name = target.id if isinstance(target, ast.Name) else getattr(target, "attr", None)
                if name == "require_feature" and dec.args and isinstance(dec.args[0], ast.Constant):
                    keys.append(dec.args[0].value)
            return keys
    return keys


def _gate_cases() -> list[tuple[str, str, str]]:
    """Flatten REQUIRED_GATES into (toggle_key, file_rel, func_name) tuples."""
    return [(toggle, file_rel, func) for toggle, endpoints in REQUIRED_GATES.items() for file_rel, func in endpoints]


@pytest.mark.skipif(not _gate_cases(), reason="REQUIRED_GATES is empty (Phase 1: library only)")
@pytest.mark.parametrize("toggle_key,file_rel,func_name", _gate_cases())
def test_endpoint_has_feature_gate(toggle_key: str, file_rel: str, func_name: str) -> None:
    """Every endpoint declared in REQUIRED_GATES must carry its gate."""
    file_path = REPO_ROOT / file_rel
    assert (
        file_path.exists()
    ), f"Handler file not found: {file_path}\nIf this endpoint moved, update REQUIRED_GATES in this test."

    tree = ast.parse(file_path.read_text())
    decorators = _decorators_for_function(tree, func_name)
    assert "require_feature" in decorators, (
        f"Function '{func_name}' in {file_rel} is missing @require_feature(\"{toggle_key}\").\n"
        f"This endpoint serves feature '{toggle_key}' and MUST be gated."
    )

    keys = _require_feature_keys_for_function(tree, func_name)
    assert toggle_key in keys, (
        f"Function '{func_name}' in {file_rel} is gated with {keys or 'no key'}, "
        f"but must be gated for '{toggle_key}'.\nCheck the @require_feature argument."
    )


# ---------------------------------------------------------------------------
# Tests for the AST audit mechanism itself.
# ---------------------------------------------------------------------------

_FIXTURE_SOURCE = """
from lisa.utilities.feature_gate import require_feature


@require_feature("deleteSessionHistory")
def gated_traditional(event, context):
    return {}


@some_other_decorator
def ungated(event, context):
    return {}
"""


@pytest.fixture(scope="module")
def fixture_tree() -> ast.AST:
    return ast.parse(_FIXTURE_SOURCE)


def test_detects_require_feature_decorator(fixture_tree: ast.AST) -> None:
    assert "require_feature" in _decorators_for_function(fixture_tree, "gated_traditional")


def test_does_not_falsely_detect_gate_on_ungated_function(fixture_tree: ast.AST) -> None:
    decorators = _decorators_for_function(fixture_tree, "ungated")
    assert "require_feature" not in decorators


def test_decorators_for_missing_function_returns_empty(fixture_tree: ast.AST) -> None:
    assert _decorators_for_function(fixture_tree, "does_not_exist") == []


def test_extracts_require_feature_key(fixture_tree: ast.AST) -> None:
    assert _require_feature_keys_for_function(fixture_tree, "gated_traditional") == ["deleteSessionHistory"]


def test_no_require_feature_key_for_ungated_function(fixture_tree: ast.AST) -> None:
    assert _require_feature_keys_for_function(fixture_tree, "ungated") == []


def test_required_gates_paths_resolve() -> None:
    """Guardrail: every path in REQUIRED_GATES must exist. Catches typos and
    file moves as the map grows per phase."""
    for toggle, endpoints in REQUIRED_GATES.items():
        for file_rel, _func in endpoints:
            assert (REPO_ROOT / file_rel).exists(), f"REQUIRED_GATES path does not exist: {file_rel} (toggle {toggle})"
