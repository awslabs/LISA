#!/bin/bash
# Runs the lisa-sdk pytest as an integration test

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$PROJECT_DIR"

# Load config from shared module
eval "$(node scripts/integration-env.mjs env)"

# Parse args
ALB_URL=""
API_URL=""
VERIFY="${VERIFY:-false}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --alb-url|-a) ALB_URL="$2"; shift 2 ;;
    --rest-url|-r) API_URL="$2"; shift 2 ;;
    --verify|-v) VERIFY="$2"; shift 2 ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo "  --rest-url, -r   URL to the LISA REST API"
      echo "  --alb-url, -a    URL to the ALB (alternate)"
      echo "  --verify, -v     SSL verify: true/false"
      exit 0
      ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

[[ -z "$ALB_URL" ]] && ALB_URL=$(node scripts/integration-env.mjs alb-url)
[[ -z "$API_URL" ]] && API_URL=$(node scripts/integration-env.mjs api-url)

echo "Using: PROFILE=${PROFILE}, DEPLOYMENT_NAME=${DEPLOYMENT_NAME}, APP_NAME=${APP_NAME}, DEPLOYMENT_STAGE=${DEPLOYMENT_STAGE}, REGION=${REGION}"
echo "VERIFY=${VERIFY}, API_URL=${API_URL}, ALB_URL=${ALB_URL}"

pytest lisa-sdk --url "$ALB_URL" --api "$API_URL" --verify "$VERIFY" --profile "$PROFILE" -n auto
