# LISA SDK Integration Tests

This directory contains integration tests for the LISA SDK that require a deployed LISA environment to run.

## Test Files

- `test_api.py` - Tests basic API operations (list models, repositories, configs, sessions)
- `test_models.py` - Tests LisaLlm model listing
- `test_llm_proxy.py` - Tests LLM proxy operations (mostly skipped, require specific models)
- `test_rag.py` - Tests RAG operations (mostly skipped, require deployed environment)
- `conftest.py` - Fixtures and configuration for integration tests

## Prerequisites

These tests require:

1. **Deployed LISA Environment** - A running LISA deployment in AWS
2. **AWS Credentials** - Configured AWS credentials with access to:
   - Secrets Manager (for API key retrieval)
   - DynamoDB (for token management)
3. **Command Line Arguments:**
   - `--url` or `--api` - REST API or API Gateway URL
   - `--region` - AWS region (default: us-west-2)
   - `--deployment` - Deployment name (default: app)
   - `--profile` - AWS profile (default: default)
   - `--verify` - SSL verification (default: false)
   - `--stage` - Deployment stage (default: dev)

## Running Integration Tests

### Basic Usage

```bash
pytest test/integration/sdk/ \
  --api https://your-api-gateway-url.execute-api.us-west-2.amazonaws.com/prod \
  --region us-west-2 \
  --deployment my-deployment \
  --profile my-aws-profile
```

### Using REST URL

```bash
pytest test/integration/sdk/ \
  --url https://your-rest-url.elb.amazonaws.com/lisa \
  --region us-west-2
```

### Run Specific Test File

```bash
pytest test/integration/sdk/test_api.py -v \
  --api https://your-api-url.com \
  --region us-west-2
```

## Test Behavior

- **Authentication**: Tests automatically retrieve the management API key from AWS Secrets Manager
- **Token Management**: Tests create temporary tokens in DynamoDB and clean them up after execution
- **Skipped Tests**: Many tests are skipped because they require specific models or configurations to be deployed

## Differences from Unit Tests

| Aspect | Unit Tests | Integration Tests |
|--------|-----------|-------------------|
| Location | `test/lisa-sdk/` | `test/integration/sdk/` |
| Dependencies | None (mocked) | Deployed LISA environment |
| Speed | Fast (~0.1s) | Slow (network calls) |
| Isolation | Fully isolated | Requires AWS resources |
| Purpose | Test SDK logic | Test end-to-end functionality |

## Adding New Integration Tests

When adding new integration tests:

1. Place them in this directory (`test/integration/sdk/`)
2. Use the fixtures from `conftest.py` for authentication
3. Add `pytest.skip()` decorators for tests that require specific configurations
4. Document any special requirements in this README
5. Clean up any resources created during tests

## Common Issues

### Authentication Errors

If you see authentication errors:
- Verify AWS credentials are configured correctly
- Check that the deployment name matches your LISA deployment
- Ensure the management key exists in Secrets Manager

### Connection Errors

If you see connection errors:
- Verify the API URL is correct and accessible
- Check SSL verification settings (`--verify false` for self-signed certs)
- Ensure network connectivity to the LISA deployment

### Skipped Tests

Many tests are skipped by default because they require:
- Specific models to be deployed (TGI, instructor embeddings, etc.)
- Specific configurations (API Gateway vs REST URL)
- Management tokens (not all deployments support this)

This is expected behavior and not an error.
