# LISA Test Structure

This directory contains all tests for the LISA monorepo, organized by module.

## Directory Structure

```
test/
├── cdk/              # CDK infrastructure tests
├── lambda/           # Lambda function tests
├── mcp-workbench/    # MCP Workbench module tests
├── lisa-sdk/         # LISA SDK (lisapy) tests
├── python/           # Integration tests
└── utils/            # Test utilities
```

## Running Tests

### Run all tests
```bash
pytest
```

### Run tests for a specific module
```bash
# MCP Workbench tests
pytest test/mcp-workbench/

# LISA SDK tests
pytest test/lisa-sdk/

# Lambda tests
pytest test/lambda/
```

### Run a specific test file
```bash
pytest test/mcp-workbench/test_core.py
```

## Module Test Organization

### MCP Workbench (`test/mcp-workbench/`)
Tests for the MCP Workbench module located in `lib/serve/mcp-workbench/src/mcpworkbench/`

### LISA SDK (`test/lisa-sdk/`)
Tests for the LISA Python SDK located in `lisa-sdk/lisapy/`

### Lambda (`test/lambda/`)
Tests for Lambda functions located in `lambda/`

## Configuration

Tests are configured in:
- `pytest.ini` - Main pytest configuration with PYTHONPATH settings
- `pyproject.toml` - Additional pytest and mypy configuration

The PYTHONPATH is configured to include:
- `lambda/`
- `lisa-sdk/`
- `lib/serve/rest-api/src/`
- `lib/serve/mcp-workbench/src/`

This allows tests to import modules from their respective source directories.

## Type Checking

Run mypy type checking:
```bash
mypy --config-file=pyproject.toml lisa-sdk/ lib/serve/mcp-workbench/src/
```

The mypy configuration uses `explicit_package_bases` to properly handle the monorepo structure and avoid duplicate module errors.
