#!/bin/bash
# Integration setup test - deploys resources to LISA and runs tests

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

# Load config from shared module
eval "$(node scripts/integration-env.mjs env)"

# Validate AWS credentials
node scripts/integration-env.mjs validate

# Parse args
ALB_URL=""
API_URL=""
VERIFY="${VERIFY:-true}"
CLEANUP=false
SKIP_CREATE=false
WAIT=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --alb-url|-a) ALB_URL="$2"; shift 2 ;;
    --rest-url|-r) API_URL="$2"; shift 2 ;;
    --verify|-v) VERIFY="$2"; shift 2 ;;
    --cleanup|-c) CLEANUP=true; shift ;;
    --skip-create|-sc) SKIP_CREATE=true; shift ;;
    --wait|-w) WAIT=true; shift ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo "  --rest-url, -r    URL to the LISA REST API"
      echo "  --alb-url, -a     URL to the ALB"
      echo "  --verify, -v      SSL verify (true/false)"
      echo "  --cleanup, -c    Clean up resources after"
      echo "  --skip-create, -sc  Skip resource creation"
      echo "  --wait, -w       Wait for resources"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

[[ -z "$ALB_URL" ]] && ALB_URL=$(node scripts/integration-env.mjs alb-url)
[[ -z "$API_URL" ]] && API_URL=$(node scripts/integration-env.mjs api-url)

if [[ -z "$ALB_URL" || -z "$API_URL" ]]; then
  echo "Error: ALB_URL and API_URL required. Provide with --alb-url and --rest-url"
  exit 1
fi

AWS_ARGS=""
[[ -n "$PROFILE" ]] && AWS_ARGS="--profile $PROFILE"

echo "Using: PREFIX=${PREFIX}, REGION=${REGION}"
echo "ALB: ${ALB_URL}"
echo "API: ${API_URL}"

PYTHON_ARGS="--url $ALB_URL --api $API_URL --deployment-name $DEPLOYMENT_NAME --deployment-stage $DEPLOYMENT_STAGE --deployment-prefix $PREFIX --verify $VERIFY --region $REGION"
[[ -n "$PROFILE" ]] && PYTHON_ARGS="$PYTHON_ARGS --profile $PROFILE"
[[ "$CLEANUP" == true ]] && PYTHON_ARGS="$PYTHON_ARGS --cleanup"
[[ "$SKIP_CREATE" == true ]] && PYTHON_ARGS="$PYTHON_ARGS --skip-create"
[[ "$WAIT" == true ]] && PYTHON_ARGS="$PYTHON_ARGS --wait"

export AWS_DEFAULT_REGION="${REGION}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "${SCRIPT_DIR}/integration-setup-test.py" $PYTHON_ARGS
