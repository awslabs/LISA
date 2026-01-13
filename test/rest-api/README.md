# REST API Unit Tests

This directory contains unit tests for the LISA REST API (`lib/serve/rest-api/src`).

## Test Structure

```
test/rest-api/
├── conftest.py          # Shared fixtures and test configuration
├── test_utils.py        # Tests for utility modules (cache, decorators, resources)
├── test_routes.py       # Tests for API routes and health check
└── README.md            # This file
```

## Current Test Coverage

### Utils Module (11 tests) ✅
- **Cache Manager**: Set/get cache, persistence, updates
- **Singleton Decorator**: Single instance creation, state preservation
- **Resources**: ModelType and RestApiResource enums

### Routes Module (7 tests) ✅
- **Health Check**: Success and failure scenarios
- **Middleware**: Request ID, CORS, exception handling
- **Auth Integration**: Enabled/disabled authentication

**Total: 18 passing tests**

## Running Tests

### Run All REST API Tests

```bash
pytest test/rest-api -v
```

### Run Specific Test File

```bash
pytest test/rest-api/test_utils.py -v
```

### Run with Coverage

```bash
pytest test/rest-api --cov=lib/serve/rest-api/src --cov-report=html
```

### Run via Make

```bash
make test-rest-api
```

## Test Approach

These tests follow the principle of **high-level, isolated testing**:

1. **Fully Isolated** - No external dependencies (AWS, databases, etc.)
2. **Mocked Dependencies** - All AWS services and external calls are mocked
3. **Fast Execution** - All tests run in ~0.1 seconds
4. **Focused Testing** - Tests focus on business logic, not implementation details

## Module Import Challenges

The REST API uses relative imports (e.g., `from .utils import ...`) which makes direct testing challenging. Our approach:

1. **Add src to path**: Tests add `lib/serve/rest-api/src` to `sys.path`
2. **Import modules directly**: Import from module names (e.g., `from utils import ...`)
3. **Test public interfaces**: Focus on testing exported functions and classes

## Authentication Testing Note

The `auth.py` module uses complex relative imports and external dependencies (JWT, boto3, etc.). Full unit testing of authentication would require:

- Mocking JWT validation
- Mocking boto3 clients (DynamoDB, Secrets Manager)
- Mocking OIDC endpoints

For now, authentication is tested at the integration level through the routes tests (auth enabled/disabled scenarios).

## Future Enhancements

Potential improvements to the test suite:

- [ ] Add tests for handler modules (embeddings, generation, models)
- [ ] Add tests for LiteLLM passthrough endpoints
- [ ] Add tests for guardrails functionality
- [ ] Add tests for metrics collection
- [ ] Add integration tests with FastAPI TestClient
- [ ] Add tests for request/response validation
- [ ] Add tests for error handling scenarios

## Dependencies

The REST API tests require:

- `fastapi` - Web framework
- `pytest` - Testing framework
- `pytest-asyncio` - Async test support

These are already included in the main project dependencies.

## CI/CD Integration

These tests are included in:

- `make test` - Run all unit tests
- `make test-coverage` - Run with coverage reporting
- `make test-rest-api` - Run only REST API tests

The tests are fast and have no external dependencies, making them ideal for CI/CD pipelines.
