# LISA Integration Tests

This directory contains integration tests for the LISA (Large Language Model Infrastructure for Scalable Applications) project.

## Files

- `integration-test.sh` - Original integration test that runs the lisa-sdk pytest suite
- `integration-setup-test.sh` - New integration test that deploys LISA resources
- `integration-setup-test.py` - Python script for resource deployment testing

## Integration Setup Test

The `integration-setup-test.sh` script creates and optionally cleans up LISA resources for testing purposes. This script is designed to test the full deployment pipeline including:

1. **Bedrock Model** - Creates a Claude 3 Haiku model configuration using Amazon Bedrock
2. **Self-Hosted Model** - Deploys a Llama 2 7B model using LISA's self-hosting capabilities  
3. **PGVector Repository** - Creates a PostgreSQL vector store for RAG operations
4. **OpenSearch Repository** - Creates an OpenSearch cluster for vector storage

### Usage

The script uses the same authentication setup as the original `integration-test.sh` and automatically reads configuration from `config-custom.yaml`.

#### Basic Usage

```bash
# Deploy resources with automatic cleanup
./test/python/integration-setup-test.sh --cleanup

# Deploy resources and wait for them to be ready
./test/python/integration-setup-test.sh --wait

# Deploy resources, wait for readiness, then clean up
./test/python/integration-setup-test.sh --wait --cleanup
```

#### Advanced Usage

```bash
# Specify custom API endpoints
./test/python/integration-setup-test.sh --rest-url https://your-api.com --cleanup

# Disable SSL verification for development
./test/python/integration-setup-test.sh --verify false --cleanup
```

### Command Line Options

- `--rest-url, -r` - URL to the LISA REST API (auto-detected from CloudFormation if not provided)
- `--verify, -v` - SSL certificate verification ('true' or 'false', defaults to 'false')  
- `--cleanup, -c` - Clean up all created resources after deployment
- `--wait, -w` - Wait for resources to reach ready state before completing
- `--help, -h` - Display help message

### Prerequisites

1. **AWS Configuration**: Ensure AWS credentials are configured with appropriate permissions for LISA deployment
2. **LISA Deployment**: A running LISA instance with API endpoints accessible
3. **Configuration File**: Valid `config-custom.yaml` with deployment settings
4. **Dependencies**: Python 3 and required packages (automatically handled by lisa-sdk)

### What Gets Created

The test creates the following resources with predictable names for easy identification:

- **Models:**
  - `bedrock-claude-v3-haiku` - Bedrock Claude 3 Haiku model
  - `self-hosted-llama2-7b` - Self-hosted Llama 2 7B model

- **Repositories:**  
  - `test-pgvector-repo` - PGVector repository with new RDS instance
  - `test-opensearch-repo` - OpenSearch repository with new cluster

### Resource Lifecycle

#### Without --cleanup flag:
Resources remain deployed for manual testing and must be cleaned up through:
- LISA UI (Model Management and Configuration pages)
- Running the script again with `--cleanup`
- Manual AWS resource deletion

#### With --cleanup flag:
All created resources are automatically deleted at the end of the test run.

#### With --wait flag:
Script monitors resource deployment status and waits up to 30 minutes for each resource to become ready. Useful for validating full deployment pipeline.

### Exit Codes

- `0` - Success (all resources created and optionally cleaned up)
- `1` - Failure (resource creation failed or other error)

### Examples

```bash
# Quick test - deploy and immediately clean up
./test/python/integration-setup-test.sh -c

# Full integration test - deploy, wait for ready, then clean up  
./test/python/integration-setup-test.sh -w -c

# Deploy for manual testing (resources remain)
./test/python/integration-setup-test.sh

# Clean up resources from previous test
./test/python/integration-setup-test.sh -c
```

## SDK Extensions

The integration setup test includes new SDK functions in the lisa-sdk package:

### Model Management
- `create_bedrock_model()` - Create Bedrock model configurations
- `create_self_hosted_model()` - Deploy self-hosted models with full configuration
- `delete_model()` - Remove models from LISA
- `get_model()` - Retrieve model details and status

### Repository Management  
- `create_repository()` - Generic repository creation
- `create_pgvector_repository()` - Create PGVector repositories with RDS
- `create_opensearch_repository()` - Create OpenSearch repositories with clusters
- `delete_repository()` - Remove repositories and associated resources
- `get_repository_status()` - Check repository deployment status

These functions provide comprehensive programmatic access to LISA's resource management capabilities and can be used in other automation scripts and applications.
