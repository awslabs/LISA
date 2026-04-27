#!/bin/bash
set -e

# Check the necessary environment variables
declare -a vars=("SAGEMAKER_BASE_DIR" "S3_BUCKET_MODELS" "MODEL_NAME" "LOCAL_CODE_PATH")
for var in "${vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        echo "$var must be set"
        exit 1
    fi
done

# Set environment variables
echo "Setting environment variables"
export TS_DISABLE_SYSTEM_METRICS=1
export TS_ENABLE_METRICS_API=0
export TS_METRICS_ENABLE="false"
export TS_ASYNC_LOGGING=0
echo "$(env)"

# Download the model repo
echo "Downloading S3 model repository s3://${S3_BUCKET_MODELS}/${MODEL_NAME}/ to ${SAGEMAKER_BASE_DIR}/model/"
s5cmd sync s3://${S3_BUCKET_MODELS}/${MODEL_NAME}/* ${SAGEMAKER_BASE_DIR}/model/

# Copy model code into the directory
echo "Copying model code ${LOCAL_CODE_PATH} into ${SAGEMAKER_BASE_DIR}/model/code"
mkdir -p ${SAGEMAKER_BASE_DIR}/model/code
cp -r ${LOCAL_CODE_PATH}/* ${SAGEMAKER_BASE_DIR}/model/code

# Start webserver
echo "Starting webserver"
python /usr/local/bin/dockerd-entrypoint.py serve
