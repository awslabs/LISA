#!/bin/bash
# Runs the lisa-sdk pytest as an integration test

PROJECT_DIR="$(pwd)"
PROFILE=$(cat ${PROJECT_DIR}/config-custom.yaml | yq -r .profile)
REGION=$(cat ${PROJECT_DIR}/config-custom.yaml | yq -r .region)
DEPLOYMENT_NAME=$(cat ${PROJECT_DIR}/config-custom.yaml | yq -r .deploymentName)
APP_NAME=$(cat ${PROJECT_DIR}/config-custom.yaml | yq -r .appName)
DEPLOYMENT_STAGE=$(cat ${PROJECT_DIR}/config-custom.yaml | yq -r .deploymentStage)

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
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo "Options:"
      echo "  --rest-url, -r         URL to the LISA RESTAPI."
      echo "  --verify, -v           Path to cert, the strings 'false' or 'true'."
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

if [ -z $ALB_URL ]; then
#  ALB_URL=$(aws cloudformation describe-stacks --stack-name ${DEPLOYMENT_NAME}-${APP_NAME}-serve-${DEPLOYMENT_STAGE} --region ${REGION} \
#  --query "Stacks[0].Outputs[?OutputKey=='${OUTPUT_KEY}'].OutputValue" --output text)
  echo "Grabbing ALB from SSM"
  ALB_URL=$(aws ssm get-parameter \
      --name "/${DEPLOYMENT_STAGE}/${DEPLOYMENT_NAME}/${APP_NAME}/lisaServeRestApiUri" \
      --query "Parameter.Value" \
      --output text)
  echo "Using ALB: ${ALB_URL}"
fi

if [ -z $API_URL ]; then
  echo "Grabbing API from CFN"
  API_URL=$(aws cloudformation describe-stacks --stack-name ${DEPLOYMENT_NAME}-${APP_NAME}-api-deployment-${DEPLOYMENT_STAGE} --region ${REGION} \
        --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)
  echo "Using API: ${API_URL}"
  #api_url_ssm_key=/${DEPLOYMENT_STAGE}/${DEPLOYMENT_NAME}/${APP_NAME}/LisaApiUrl
fi

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
TEST_DIR=${SCRIPT_DIR}/../../lisa-sdk/
pytest $TEST_DIR --url $ALB_URL --api $API_URL --verify $VERIFY --profile $PROFILE -n auto
