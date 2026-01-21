#!/bin/bash
# Integration setup test script that deploys resources to LISA
# Uses the existing authentication setup from integration-test.sh

PROJECT_DIR="$(pwd)/../../"

# Read config values with defaults for missing fields
PROFILE=$(cat ${PROJECT_DIR}/config-custom.yaml | yq -r '.profile // "default"')
REGION=$(cat ${PROJECT_DIR}/config-custom.yaml | yq -r '.region // "us-west-2"')
DEPLOYMENT_NAME=$(cat ${PROJECT_DIR}/config-custom.yaml | yq -r '.deploymentName // "prod"')
APP_NAME=$(cat ${PROJECT_DIR}/config-custom.yaml | yq -r '.appName // "lisa"')
DEPLOYMENT_STAGE=$(cat ${PROJECT_DIR}/config-custom.yaml | yq -r '.deploymentStage // "prod"')

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

# Default values
CLEANUP=false
WAIT=false
SKIP_CREATE=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --alb-url|-a)
      ALB_URL="$2"
      shift 2
      ;;
    --rest-url|-r)
      API_URL="$2"
      shift 2
      ;;
    --verify|-v)
      VERIFY="$2"
      shift 2
      ;;
    --cleanup|-c)
      CLEANUP=true
      shift
      ;;
    --skip-create|-sc)
      SKIP_CREATE=true
      shift
      ;;
    --wait|-w)
      WAIT=true
      shift
      ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo "Options:"
      echo "  --rest-url, -r         URL to the LISA REST API."
      echo "  --verify, -v           Path to cert, the strings 'false' or 'true'."
      echo "  --cleanup, -c          Clean up resources after creation."
      echo "  --skip-create, -sc     Skip create of resources."
      echo "  --wait, -w             Wait for resources to be ready."
      echo "  --help, -h             Display this help message."
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

if [ -z $VERIFY ]; then
  VERIFY=false
fi

echo "Using settings: PROFILE-${PROFILE}, DEPLOYMENT_NAME-${DEPLOYMENT_NAME}, APP_NAME-${APP_NAME}, DEPLOYMENT_STAGE-${DEPLOYMENT_STAGE}, REGION-${REGION}, VERIFY-${VERIFY}, API_URL-${API_URL}, ALB_URL-${ALB_URL}"
PREFIX="/${DEPLOYMENT_STAGE}/${DEPLOYMENT_NAME}/${APP_NAME}"
echo "Prefix: ${PREFIX}"

# Check for AWS credentials - try with env vars first, then profile
AWS_ARGS=""
if [ -n "${AWS_ACCESS_KEY_ID}" ] && [ -n "${AWS_SECRET_ACCESS_KEY}" ]; then
  echo "Using AWS credentials from environment variables"
  if ! aws sts get-caller-identity --region "${REGION}" &>/dev/null; then
    echo "❌ Error: AWS credentials from environment are invalid"
    exit 1
  fi
else
  echo "Using AWS profile: ${PROFILE}"
  AWS_ARGS="--profile ${PROFILE}"
  if ! aws sts get-caller-identity ${AWS_ARGS} --region "${REGION}" &>/dev/null; then
    echo "❌ Error: AWS credentials not configured for profile '${PROFILE}'"
    exit 1
  fi
fi

if [ -z "$ALB_URL" ]; then
  echo "Grabbing ALB from SSM..."
  SSM_PARAM="${PREFIX}/lisaServeRestApiUri"
  echo "  Checking SSM parameter: ${SSM_PARAM}"
  echo "  Using profile: ${PROFILE}, region: ${REGION}"
  ALB_URL=$(aws ssm get-parameter \
      --name "${SSM_PARAM}" \
      --region "${REGION}" \
      ${AWS_ARGS} \
      --query "Parameter.Value" \
      --output text 2>&1)
  ALB_EXIT_CODE=$?

  if [ $ALB_EXIT_CODE -ne 0 ]; then
    echo "  ❌ SSM parameter not found or access denied"
    ALB_URL=""
  elif [ -z "$ALB_URL" ] || [ "$ALB_URL" = "None" ]; then
    echo "⚠️  Could not retrieve ALB URL from SSM. You may need to provide it manually with --alb-url"
    ALB_URL=""
  else
    echo "✓ Using ALB: ${ALB_URL}"
  fi
fi

if [ -z "$API_URL" ]; then
  echo "Grabbing API from SSM..."
  SSM_PARAM="${PREFIX}/LisaApiUrl"
  echo "  Checking SSM parameter: ${SSM_PARAM}"
  echo "  Using profile: ${PROFILE}, region: ${REGION}"
  API_URL=$(aws ssm get-parameter \
      --name "${SSM_PARAM}" \
      --region "${REGION}" \
      ${AWS_ARGS} \
      --query "Parameter.Value" \
      --output text 2>&1)
  API_EXIT_CODE=$?

  if [ $API_EXIT_CODE -ne 0 ]; then
    echo "  ❌ SSM parameter not found or access denied"
    API_URL=""
  elif [ -z "$API_URL" ] || [ "$API_URL" = "None" ]; then
    echo "⚠️  Could not retrieve API URL from SSM. You may need to provide it manually with --rest-url"
    API_URL=""
  else
    echo "✓ Using API: ${API_URL}"
  fi
fi

# Validate required URLs
if [ -z "$ALB_URL" ] || [ -z "$API_URL" ]; then
  echo ""
  echo "❌ Error: Required URLs are missing!"
  echo ""
  echo "ALB URL: ${ALB_URL:-'NOT SET'}"
  echo "API URL: ${API_URL:-'NOT SET'}"
  echo ""
  echo "Please provide URLs manually:"
  echo "  $0 --alb-url <ALB_URL> --rest-url <API_URL>"
  echo ""
  echo "Example:"
  echo "  $0 --alb-url https://your-alb.elb.amazonaws.com --rest-url https://your-api.execute-api.us-west-2.amazonaws.com"
  echo ""
  exit 1
fi

# Construct Python script arguments
PYTHON_ARGS="--url $ALB_URL --api $API_URL --deployment-name $DEPLOYMENT_NAME --deployment-stage $DEPLOYMENT_STAGE --deployment-prefix $PREFIX --verify $VERIFY"

if [ ! -z "$PROFILE" ]; then
  PYTHON_ARGS="$PYTHON_ARGS --profile $PROFILE"
fi

if [ "$CLEANUP" = true ]; then
  PYTHON_ARGS="$PYTHON_ARGS --cleanup"
fi

if [ "$SKIP_CREATE" = true ]; then
  PYTHON_ARGS="$PYTHON_ARGS --skip-create"
fi

if [ "$WAIT" = true ]; then
  PYTHON_ARGS="$PYTHON_ARGS --wait"
fi

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
PYTHON_SCRIPT="${SCRIPT_DIR}/integration-setup-test.py"

echo ""
echo "🚀 Running integration setup test..."
echo "Command: python3 $PYTHON_SCRIPT $PYTHON_ARGS"
echo ""

# Run the Python integration setup test
python3 "$PYTHON_SCRIPT" $PYTHON_ARGS
