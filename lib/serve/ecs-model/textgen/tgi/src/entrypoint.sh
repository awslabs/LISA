#!/bin/bash
set -e

declare -a vars=("S3_BUCKET_MODELS" "LOCAL_MODEL_PATH" "MODEL_NAME" "S3_MOUNT_POINT" "THREADS")

# Check the necessary environment variables
for var in "${vars[@]}"; do
    if [[ -z "${!var}" ]]; then
        echo "$var must be set"
        exit 1
    fi
done

# Create S3 mount point to ephemeral NVMe drive
echo "Creating S3 mountpoint for bucket ${S3_BUCKET_MODELS} at container mount point path ${S3_MOUNT_POINT}/${MODEL_NAME}"
mkdir -p ${S3_MOUNT_POINT}
mount-s3 ${S3_BUCKET_MODELS} ${S3_MOUNT_POINT}

echo "Downloading model ${S3_BUCKET_MODELS} to container path ${LOCAL_MODEL_PATH}"
mkdir -p ${LOCAL_MODEL_PATH}

# Use rsync with S3_MOUNT_POINT
ls ${S3_MOUNT_POINT}/${MODEL_NAME} | xargs -n1 -P${THREADS} -I% rsync -Pa --exclude "*.bin" ${S3_MOUNT_POINT}/${MODEL_NAME}/% ${LOCAL_MODEL_PATH}/

# Required params
echo "Setting environment variables"
export MAX_CONCURRENT_REQUESTS="${MAX_CONCURRENT_REQUESTS}"
export MAX_INPUT_LENGTH="${MAX_INPUT_LENGTH}"
export MAX_TOTAL_TOKENS="${MAX_TOTAL_TOKENS}"
if [[ -n "${QUANTIZE}" ]]; then
  export QUANTIZE="${QUANTIZE}"
fi
echo "$(env)"

# Start the webserver
echo "Starting TGI"
text-generation-launcher --model-id $LOCAL_MODEL_PATH --port 8080 --json-output
