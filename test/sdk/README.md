# LISA SDK Unit Tests

This directory contains comprehensive unit tests for the LISA SDK (`lisapy`). These tests are fully isolated and use mocked HTTP responses to test SDK functionality without requiring a deployed LISA environment.

## Test Structure

The tests are organized by SDK mixin, with one test file per mixin:

```
test/sdk/
├── conftest.py              # Shared fixtures and test configuration
├── test_model.py            # Tests for ModelMixin (model operations)
├── test_repository.py       # Tests for RepositoryMixin (repository operations)
├── test_collection.py       # Tests for CollectionMixin (collection operations)
├── test_rag.py              # Tests for RagMixin (document and RAG operations)
├── test_config.py           # Tests for ConfigMixin (configuration operations)
├── test_session.py          # Tests for SessionMixin (session operations)
└── test_docs.py             # Tests for DocsMixin (documentation operations)
```

## Testing Approach

### HTTP Mocking with `responses`

These tests use the [`responses`](https://github.com/getsentry/responses) library to mock HTTP requests at the `requests` library level. This approach:

- ✅ Tests the actual HTTP request/response flow
- ✅ Validates request formatting, headers, and URL construction
- ✅ Catches serialization/deserialization issues
- ✅ Provides realistic testing without network calls
- ✅ Runs fast (all 57 tests in ~0.1 seconds)

### Example Test Pattern

```python
@responses.activate
def test_list_models(self, lisa_api: LisaApi, api_url: str, mock_models_response: Dict):
    """Test listing all models."""
    # Mock the HTTP response
    responses.add(responses.GET, f"{api_url}/models", json=mock_models_response, status=200)

    # Call the SDK method
    models = lisa_api.list_models()

    # Assert the results
    assert len(models) == 3
    assert models[0]["modelId"] == "anthropic.claude-v2"
```

## Running Tests

### Run All SDK Unit Tests

```bash
pytest test/sdk -v
```

### Run Specific Test File

```bash
pytest test/sdk/test_model.py -v
```

### Run Specific Test Class

```bash
pytest test/sdk/test_model.py::TestModelMixin -v
```

### Run Specific Test

```bash
pytest test/sdk/test_model.py::TestModelMixin::test_list_models -v
```

### Run with Coverage

```bash
pytest test/sdk --cov=lisa-sdk/lisapy --cov-report=html
```

## Test Coverage

The test suite provides comprehensive coverage of all SDK operations:

### ModelMixin (11 tests)
- ✅ List models
- ✅ List embedding models
- ✅ List instance types
- ✅ Create Bedrock model
- ✅ Create self-hosted model
- ✅ Create self-hosted embedding model
- ✅ Delete model
- ✅ Get model by ID
- ✅ Error handling

### RepositoryMixin (10 tests)
- ✅ List repositories
- ✅ Create repository
- ✅ Create PGVector repository
- ✅ Create OpenSearch repository (with/without custom config)
- ✅ Delete repository
- ✅ Get repository status
- ✅ Error handling

### CollectionMixin (14 tests)
- ✅ Create collection (basic, with chunking, with metadata)
- ✅ Get collection
- ✅ Update collection (name, description, status)
- ✅ Delete collection
- ✅ List collections (with pagination, filters, sorting)
- ✅ Get user collections (across all repositories)
- ✅ Error handling

### RagMixin (13 tests)
- ✅ List documents
- ✅ Get document by ID
- ✅ Delete documents (by IDs, by name)
- ✅ Get presigned URL
- ✅ Upload document
- ✅ Ingest document (basic, with custom chunking)
- ✅ Similarity search (with collection ID, with model name)
- ✅ Error handling

### ConfigMixin (4 tests)
- ✅ Get configs (global, custom scope)
- ✅ Empty configs
- ✅ Error handling

### SessionMixin (5 tests)
- ✅ List sessions
- ✅ Get session by user
- ✅ Empty sessions
- ✅ Error handling

### DocsMixin (2 tests)
- ✅ Get API documentation
- ✅ Error handling

**Total: 57 tests, all passing**

## Fixtures

### Core Fixtures (conftest.py)

- `api_url` - Base API URL for testing
- `api_headers` - API headers with authentication
- `lisa_api` - Configured LisaApi instance
- `mock_responses` - Activated responses mock

### Mock Response Fixtures

- `mock_models_response` - Sample models data
- `mock_repositories_response` - Sample repositories data
- `mock_collections_response` - Sample collections data
- `mock_documents_response` - Sample documents data
- `mock_sessions_response` - Sample sessions data
- `mock_configs_response` - Sample configs data
- `mock_instances_response` - Sample instance types data

## Adding New Tests

When adding new tests:

1. **Choose the appropriate test file** based on the mixin being tested
2. **Use the `@responses.activate` decorator** to enable HTTP mocking
3. **Mock the HTTP response** using `responses.add()`
4. **Call the SDK method** being tested
5. **Assert the results** and verify request parameters
6. **Add error handling tests** for failure scenarios

### Example: Adding a New Test

```python
@responses.activate
def test_new_operation(self, lisa_api: LisaApi, api_url: str):
    """Test description."""
    # Arrange: Mock the HTTP response
    expected_response = {"result": "success"}
    responses.add(
        responses.POST,
        f"{api_url}/new-endpoint",
        json=expected_response,
        status=201
    )

    # Act: Call the SDK method
    result = lisa_api.new_operation(param="value")

    # Assert: Verify the results
    assert result["result"] == "success"

    # Verify request was made correctly
    assert len(responses.calls) == 1
    assert responses.calls[0].request.body is not None
```

## Benefits of This Approach

### Fast Execution
- All 57 tests run in ~0.1 seconds
- No network latency
- No AWS resource dependencies

### Fully Isolated
- No external dependencies
- No deployed LISA environment required
- No AWS credentials needed
- Can run in CI/CD without infrastructure

### Comprehensive Coverage
- Tests all SDK methods
- Tests error handling
- Tests request formatting
- Tests response parsing
- Tests query parameters and request bodies

### Easy to Maintain
- Clear test structure
- Reusable fixtures
- Simple mock responses
- Easy to add new tests

## Differences from Integration Tests

| Aspect | Unit Tests | Integration Tests |
|--------|-----------|-------------------|
| Location | `test/sdk/` | `test/integration/sdk/` |
| Dependencies | None (mocked) | Deployed LISA environment |
| Speed | Fast (~0.1s) | Slow (network calls) |
| Isolation | Fully isolated | Requires AWS resources |
| Purpose | Test SDK logic | Test end-to-end functionality |
| HTTP Calls | Mocked with `responses` | Real HTTP calls |
| Authentication | Mocked headers | Real AWS credentials |

## Continuous Integration

These tests are ideal for CI/CD pipelines because they:
- Run quickly
- Require no infrastructure
- Have no external dependencies
- Provide comprehensive coverage
- Catch regressions early

## Troubleshooting

### Import Errors

If you see import errors for `responses`:
```bash
pip install responses
```

### Fixture Not Found

If you see fixture errors, ensure you're running from the LISA root directory:
```bash
cd /path/to/LISA
pytest test/sdk -v
```

### Test Failures

If tests fail:
1. Check that you're using the latest SDK code
2. Verify the mock responses match the expected API format
3. Check for changes in the SDK that require test updates
4. Run with `-vv` for more detailed output

## Future Enhancements

Potential improvements to the test suite:

- [ ] Add JSON schema validation for responses
- [ ] Add tests for async operations
- [ ] Add tests for retry logic
- [ ] Add tests for timeout handling
- [ ] Add performance benchmarks
- [ ] Add tests for edge cases (empty responses, malformed data)
- [ ] Add tests for authentication flows
