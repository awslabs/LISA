# Integration Tests

This directory contains integration tests that require a deployed LISA environment to run. These tests are separated from unit tests to avoid slowing down the regular test suite and to prevent test failures when environment variables are not configured.

## Test Categories

### RAG Integration Tests (`rag/`)

End-to-end tests for RAG (Retrieval-Augmented Generation) collections functionality:
- Collection creation and management
- Document ingestion to collections
- Similarity search within collections
- Document deletion and cleanup
- Collection deletion and full cleanup

**Location:** `test/integration/rag/test_rag_collections_integration.py`

### Repository Metadata Preservation Tests

Tests for preserving pipeline metadata during repository updates. Some tests are skipped pending refactoring work.

**Location:** `test/integration/test_repository_update_metadata_preservation.py`

## Prerequisites

Integration tests require:

1. **Deployed LISA Environment** - A running LISA deployment in AWS
2. **Environment Variables:**
   - `LISA_API_URL` - URL of the deployed LISA API
   - `LISA_DEPLOYMENT_NAME` - Name of the LISA deployment
   - `AWS_DEFAULT_REGION` - AWS region where LISA is deployed
   - `LISA_VERIFY_SSL` - (Optional) Set to "false" to disable SSL verification
   - `LISA_DEPLOYMENT_STAGE` - (Optional) Deployment stage
   - `TEST_REPOSITORY_ID` - (Optional) Repository ID to use for tests (default: "test-pgvector-rag")
   - `TEST_EMBEDDING_MODEL` - (Optional) Embedding model to use (default: "titan-embed")

3. **AWS Credentials** - Configured AWS credentials with access to the LISA deployment

## Running Integration Tests

### Run All Integration Tests

```bash
make test-rag-integ
```

### Run Specific Test Suites

**RAG Collections Integration Tests:**
```bash
pytest test/integration/rag/test_rag_collections_integration.py -v
```

**Repository Metadata Preservation Tests:**
```bash
make test-metadata-integ
# or
pytest test/integration/test_repository_update_metadata_preservation.py -v
```

### Run with Custom Configuration

```bash
export LISA_API_URL="https://your-api-url.com"
export LISA_DEPLOYMENT_NAME="your-deployment"
export AWS_DEFAULT_REGION="us-east-1"
pytest test/integration -v
```

## Test Behavior

- **Skipped Tests:** Integration tests are automatically skipped if required environment variables are not set
- **Cleanup:** Tests include cleanup fixtures to remove created resources after test completion
- **Isolation:** Each test suite manages its own test data and cleans up after itself

## Excluding from Regular Test Runs

Integration tests are excluded from regular test runs via `pytest.ini`:

```ini
norecursedirs = test/integration
```

This ensures that:
- `make test` runs only unit tests (fast, no external dependencies)
- `make test-rag-integ` runs integration tests (slower, requires deployed environment)
- CI/CD pipelines can run unit tests quickly without requiring a deployed environment

## Adding New Integration Tests

When adding new integration tests:

1. Place them in the appropriate subdirectory under `test/integration/`
2. Use `pytest.skip()` to skip tests when required environment variables are missing
3. Include cleanup fixtures to remove test resources
4. Document required environment variables in this README
5. Add a new make target in the Makefile if needed
