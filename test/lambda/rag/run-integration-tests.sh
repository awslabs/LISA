#!/bin/bash
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

# Integration test runner for RAG Collections
# This script sets up the environment and runs the integration tests

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"

# Check if config file exists
CONFIG_FILE="${PROJECT_DIR}/config-custom.yaml"
if [ ! -f "$CONFIG_FILE" ]; then
  echo "⚠️  Warning: config-custom.yaml not found at ${CONFIG_FILE}"
  echo "Using default values. You can override with command line arguments."
fi

# Read config values with defaults (handle missing file gracefully)
if [ -f "$CONFIG_FILE" ]; then
  PROFILE=$(cat ${CONFIG_FILE} | yq -r '.profile // "default"' 2>/dev/null || echo "lisa")
  REGION=$(cat ${CONFIG_FILE} | yq -r '.region // "us-west-2"' 2>/dev/null || echo "us-west-2")
  DEPLOYMENT_NAME=$(cat ${CONFIG_FILE} | yq -r '.deploymentName // "lisa"' 2>/dev/null || echo "lisa")
  APP_NAME=$(cat ${CONFIG_FILE} | yq -r '.appName // "lisa"' 2>/dev/null || echo "lisa")
  DEPLOYMENT_STAGE=$(cat ${CONFIG_FILE} | yq -r '.deploymentStage // "dev"' 2>/dev/null || echo "prod")
else
  PROFILE="lisa"
  REGION="us-west-2"
  DEPLOYMENT_NAME="lisa"
  APP_NAME="lisa"
  DEPLOYMENT_STAGE="prod"
fi

# Override with null check and provide defaults
if [ "$PROFILE" = "null" ]; then
  PROFILE="default"
fi

if [ "$REGION" = "null" ]; then
  REGION="us-east-1"
fi

if [ "$DEPLOYMENT_NAME" = "null" ]; then
  DEPLOYMENT_NAME="lisa"
fi

if [ "$APP_NAME" = "null" ]; then
  APP_NAME="lisa"
fi

if [ "$DEPLOYMENT_STAGE" = "null" ]; then
  DEPLOYMENT_STAGE="dev"
fi

# Parse command line arguments
API_URL=""
VERIFY="true"
EMBEDDING_MODEL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-url|-a)
      API_URL="$2"
      shift 2
      ;;
    --verify|-v)
      VERIFY="$2"
      shift 2
      ;;
    --embedding-model|-e)
      EMBEDDING_MODEL="$2"
      shift 2
      ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo "Options:"
      echo "  --api-url, -a          URL to the LISA REST API."
      echo "  --verify, -v           Whether to verify SSL certificates (true/false)."
      echo "  --embedding-model, -e  Embedding model to use for tests."
      echo "  --help, -h             Display this help message."
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

echo "Using settings: PROFILE=${PROFILE}, DEPLOYMENT_NAME=${DEPLOYMENT_NAME}, APP_NAME=${APP_NAME}, DEPLOYMENT_STAGE=${DEPLOYMENT_STAGE}, REGION=${REGION}"

# Get API URL from CloudFormation if not provided
if [ -z "$API_URL" ]; then
  echo "Grabbing API URL from CloudFormation ${DEPLOYMENT_STAGE}-${APP_NAME}-api-deployment-${DEPLOYMENT_STAGE}..."
  API_URL=$(aws cloudformation describe-stacks \
    --stack-name ${DEPLOYMENT_STAGE}-${APP_NAME}-api-deployment-${DEPLOYMENT_STAGE} \
    --region ${REGION} \
    --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" \
    --output text 2>/dev/null || echo "")

  if [ -z "$API_URL" ] || [ "$API_URL" = "None" ]; then
    echo "❌ Error: Could not retrieve API URL from CloudFormation."
    echo "Please provide it manually with --api-url"
    exit 1
  fi
  echo "Using API: ${API_URL}"
fi

# Note: Authentication is handled by the test utilities
echo "✓ Authentication will be configured by test utilities"

# Get DynamoDB table names
COLLECTIONS_TABLE="${DEPLOYMENT_NAME}-LisaRagCollectionsTable"
DOCUMENTS_TABLE="${DEPLOYMENT_NAME}-LisaRagDocumentsTable"
SUBDOCUMENTS_TABLE="${DEPLOYMENT_NAME}-LisaRagSubDocumentsTable"

# Set environment variables for tests
export LISA_API_URL="${API_URL}"
export LISA_DEPLOYMENT_NAME="${DEPLOYMENT_NAME}"
export LISA_DEPLOYMENT_STAGE="${DEPLOYMENT_STAGE}"
export LISA_VERIFY_SSL="${VERIFY}"
export LISA_RAG_COLLECTIONS_TABLE="${COLLECTIONS_TABLE}"
export LISA_RAG_DOCUMENTS_TABLE="${DOCUMENTS_TABLE}"
export LISA_RAG_SUBDOCUMENTS_TABLE="${SUBDOCUMENTS_TABLE}"
export AWS_DEFAULT_REGION="${REGION}"
export AWS_PROFILE="${PROFILE}"

if [ -n "$EMBEDDING_MODEL" ]; then
  export TEST_EMBEDDING_MODEL="${EMBEDDING_MODEL}"
fi

echo ""
echo "🚀 Running RAG Collections Integration Tests..."
echo "API URL: ${API_URL}"
echo "Collections Table: ${COLLECTIONS_TABLE}"
echo "Documents Table: ${DOCUMENTS_TABLE}"
echo "SubDocuments Table: ${SUBDOCUMENTS_TABLE}"
echo ""

# Activate virtual environment if it exists
if [ -d "${PROJECT_DIR}/.venv" ]; then
  echo "Activating virtual environment..."
  source "${PROJECT_DIR}/.venv/bin/activate"
elif [ -d "${PROJECT_DIR}/venv" ]; then
  echo "Activating virtual environment..."
  source "${PROJECT_DIR}/venv/bin/activate"
fi

# Check if pytest is available
if ! python3 -m pytest --version &> /dev/null; then
  echo "❌ Error: pytest is not installed"
  echo ""
  echo "Please install pytest:"
  echo "  pip install pytest boto3 pyyaml"
  echo ""
  echo "Or activate your virtual environment:"
  echo "  source .venv/bin/activate"
  exit 1
fi

# Run pytest
cd "${PROJECT_DIR}"
python3 -m pytest test/lambda/rag/test_rag_collections_integration.py -v -s

echo ""
echo "✓ Integration tests completed"
