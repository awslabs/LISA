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

### SDK Integration Tests (`sdk/`)

Integration tests for the LISA SDK that test end-to-end functionality against a deployed LISA environment:
- API operations (models, repositories, configs, sessions)
- LLM proxy operations
- RAG operations

**Location:** `test/integration/sdk/`
**See:** `test/integration/sdk/README.md` for detailed documentation

## Prerequisites

All integration tests require:

1. **Deployed LISA Environment** - A running LISA deployment in AWS
2. **AWS Credentials** - Configured AWS credentials with appropriate permissions
3. **Environment Variables or CLI Arguments** - Specific to each test suite (see below)

## Running Integration Tests

### RAG Integration Tests

**Prerequisites:**
- `LISA_API_URL` - URL of the deployed LISA API
- `LISA_DEPLOYMENT_NAME` - Name of the LISA deployment
- `AWS_DEFAULT_REGION` - AWS region where LISA is deployed
- `LISA_VERIFY_SSL` - (Optional) Set to "false" to disable SSL verification
- `LISA_DEPLOYMENT_STAGE` - (Optional) Deployment stage
- `TEST_REPOSITORY_ID` - (Optional) Repository ID to use (default: "test-pgvector-rag")
- `TEST_EMBEDDING_MODEL` - (Optional) Embedding model to use (default: "titan-embed")

**Run with Make:**
```bash
make test-rag-integ
```

**Run with pytest:**
```bash
# Set environment variables
export LISA_API_URL="https://your-api-url.com"
export LISA_DEPLOYMENT_NAME="your-deployment"
export AWS_DEFAULT_REGION="us-east-1"

# Run tests
pytest test/integration/rag/test_rag_collections_integration.py -v
```

**Run with the provided script:**
```bash
cd test/integration/rag
./run-integration-tests.sh --api-url https://your-api-url.com
```

**What gets tested:**
- ✅ Collection creation and retrieval
- ✅ Document ingestion and listing
- ✅ Similarity search on collections
- ✅ Document deletion and cleanup
- ✅ User collections across repositories
- ✅ Collection deletion with documents

### SDK Integration Tests

**Prerequisites:**
- `--api` or `--url` - API Gateway URL or REST URL
- `--region` - AWS region (default: us-west-2)
- `--deployment` - Deployment name (default: app)
- `--profile` - AWS profile (default: default)
- `--verify` - SSL verification (default: false)
- `--stage` - Deployment stage (default: dev)

**Run with Make:**
```bash
make test-sdk-integ
```

**Run with pytest:**
```bash
pytest test/integration/sdk/ \
  --api https://your-api-gateway-url.execute-api.us-west-2.amazonaws.com/prod \
  --region us-west-2 \
  --deployment my-deployment \
  --profile my-aws-profile \
  -v
```

**What gets tested:**
- ✅ List models and embedding models
- ✅ List repositories
- ✅ Get configurations
- ✅ List sessions
- ✅ Get API documentation
- ⏭️ LLM proxy operations (skipped - require specific models)
- ⏭️ RAG operations (skipped - require deployed environment)

### Repository Metadata Preservation Tests

**Prerequisites:**
- Standard pytest environment (no special configuration needed)
- Tests use mocked AWS services

**Run with Make:**
```bash
make test-metadata-integ
```

**Run with pytest:**
```bash
pytest test/integration/test_repository_update_metadata_preservation.py -v
```

**What gets tested:**
- ✅ Bedrock KB updates preserve existing metadata
- ✅ Complete metadata replacement when tags provided
- ⏭️ Direct pipeline updates (skipped - pending refactoring)
- ⏭️ Partial metadata updates (skipped - pending refactoring)
- ⏭️ New collection metadata handling (skipped - pending refactoring)

## Running All Integration Tests

**Note:** This will attempt to run all integration tests. Tests that don't have required environment variables will be skipped.

```bash
pytest test/integration -v
```

## Test Behavior

- **Automatic Skipping:** Tests automatically skip if required environment variables or CLI arguments are not provided
- **Cleanup:** Tests include cleanup fixtures to remove created resources after execution
- **Isolation:** Each test suite manages its own test data and cleans up after itself
- **Timeouts:** Some tests have extended timeouts to account for infrastructure spin-up time

## Excluding from Regular Test Runs

Integration tests are excluded from regular test runs via `pytest.ini`:

```ini
norecursedirs = test/integration
```

This ensures that:
- `make test` runs only unit tests (fast, no external dependencies)
- `make test-rag-integ` runs RAG integration tests (requires deployed environment)
- `make test-sdk-integ` runs SDK integration tests (requires deployed environment)
- CI/CD pipelines can run unit tests quickly without requiring a deployed environment

## Troubleshooting

### Authentication Errors

**RAG Tests:**
- Verify environment variables are set correctly
- Check that the API URL is accessible
- Ensure AWS credentials have access to the LISA deployment

**SDK Tests:**
- Verify AWS credentials are configured correctly
- Check that the deployment name matches your LISA deployment
- Ensure the management key exists in Secrets Manager

### Connection Errors

- Verify the API URL is correct and accessible
- Check SSL verification settings (use `--verify false` for self-signed certs)
- Ensure network connectivity to the LISA deployment
- Check security groups and network ACLs

### Skipped Tests

Many tests are skipped by default because they require:
- Specific models to be deployed (TGI, instructor embeddings, etc.)
- Specific configurations (API Gateway vs REST URL)
- Management tokens (not all deployments support this)
- Deployed LISA environment with specific features enabled

This is expected behavior and not an error.

### Timeout Errors

If tests timeout:
- Increase the timeout values in the test code
- Check that the LISA deployment is healthy and responsive
- Verify that batch jobs are processing correctly
- Check CloudWatch logs for errors in Lambda functions or ECS tasks

## Adding New Integration Tests

When adding new integration tests:

1. **Choose the appropriate directory:**
   - `test/integration/rag/` for RAG-specific tests
   - `test/integration/sdk/` for SDK tests
   - `test/integration/` root for other integration tests

2. **Use appropriate fixtures:**
   - RAG tests: Use environment variables for configuration
   - SDK tests: Use CLI arguments via `conftest.py` fixtures

3. **Add skip decorators:**
   ```python
   @pytest.mark.skip(reason="Requires specific model deployment")
   def test_something():
       pass
   ```

4. **Include cleanup:**
   - Use fixtures with `yield` for setup/teardown
   - Track created resources and clean them up
   - Handle cleanup failures gracefully

5. **Document requirements:**
   - Update this README with new prerequisites
   - Add examples of how to run the new tests
   - Document what gets tested

6. **Update Make targets:**
   - Add new make targets if needed
   - Update existing targets to include new tests

## CI/CD Considerations

For CI/CD pipelines:

1. **Unit tests** should run on every commit (fast, no dependencies)
2. **Integration tests** should run:
   - On a schedule (nightly, weekly)
   - Before releases
   - In a dedicated environment with deployed LISA

3. **Environment setup:**
   - Use secrets management for credentials
   - Deploy a test LISA environment
   - Set environment variables in CI/CD configuration
   - Clean up resources after tests complete

4. **Test isolation:**
   - Use unique identifiers for test resources
   - Avoid conflicts between parallel test runs
   - Clean up resources even if tests fail

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
