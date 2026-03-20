#!/bin/bash
# Integration test runner for RAG Collections

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$PROJECT_DIR"

# Load config from shared module
eval "$(node scripts/integration-env.mjs env)"

# Parse args
API_URL=""
VERIFY="true"
EMBEDDING_MODEL=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-url|-a) API_URL="$2"; shift 2 ;;
    --verify|-v) VERIFY="$2"; shift 2 ;;
    --embedding-model|-e) EMBEDDING_MODEL="$2"; shift 2 ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo "  --api-url, -a         URL to the LISA REST API"
      echo "  --verify, -v          SSL verify (true/false)"
      echo "  --embedding-model, -e Embedding model for tests"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

[[ -z "$API_URL" ]] && API_URL=$(node scripts/integration-env.mjs api-url)

if [[ -z "$API_URL" || "$API_URL" == "None" ]]; then
  echo "Error: Could not retrieve API URL. Provide with --api-url"
  exit 1
fi

COLLECTIONS_TABLE="${DEPLOYMENT_NAME}-LisaRagCollectionsTable"
DOCUMENTS_TABLE="${DEPLOYMENT_NAME}-LisaRagDocumentsTable"
SUBDOCUMENTS_TABLE="${DEPLOYMENT_NAME}-LisaRagSubDocumentsTable"

export LISA_API_URL="${API_URL}"
export LISA_DEPLOYMENT_NAME="${DEPLOYMENT_NAME}"
export LISA_DEPLOYMENT_STAGE="${DEPLOYMENT_STAGE}"
export LISA_VERIFY_SSL="${VERIFY}"
export LISA_RAG_COLLECTIONS_TABLE="${COLLECTIONS_TABLE}"
export LISA_RAG_DOCUMENTS_TABLE="${DOCUMENTS_TABLE}"
export LISA_RAG_SUBDOCUMENTS_TABLE="${SUBDOCUMENTS_TABLE}"
export AWS_DEFAULT_REGION="${REGION}"
export AWS_PROFILE="${PROFILE}"
[[ -n "$EMBEDDING_MODEL" ]] && export TEST_EMBEDDING_MODEL="${EMBEDDING_MODEL}"

echo "Running RAG Collections Integration Tests..."
echo "API URL: ${API_URL}"

[[ -d "${PROJECT_DIR}/.venv" ]] && source "${PROJECT_DIR}/.venv/bin/activate"
[[ -d "${PROJECT_DIR}/venv" ]] && source "${PROJECT_DIR}/venv/bin/activate"

python3 -m pytest test/integration/rag/test_rag_collections_integration.py -v -s -x
