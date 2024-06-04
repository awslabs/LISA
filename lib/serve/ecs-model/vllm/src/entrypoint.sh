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

ADDITIONAL_ARGS=""
if [[ -n "${MAX_TOTAL_TOKENS}" ]]; then
  ADDITIONAL_ARGS+=" --max-model-len ${MAX_TOTAL_TOKENS}"
fi

# Start the webserver
echo "Starting vLLM"
python3 -m vllm.entrypoints.openai.api_server \
    --model ${LOCAL_MODEL_PATH} \
    --served-model-name ${MODEL_NAME} \
    --port 8080 ${ADDITIONAL_ARGS}
