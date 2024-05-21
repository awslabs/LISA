#!/bin/bash

set -e

TGI_IMAGE=""
MODEL_DIR=""
MODEL_ID=""
S3_BUCKET=""
OUTPUT_ID=""

usage(){
  cat << EOF >&2
Usage: $0
    [ -t | --tgi-image  - docker image and tag for TGI
    [ -d | --output-dir - local directory to use for model storage
    [ -m | --model-id - the huggingface model-id or path to local model dir
    [ -s | --s3-bucket - s3-bucket name (e.g. my-models-s3-bucket)
    [ -h | --help]
EOF
}

while true; do
  case "$1" in
    -t | --tgi-container )
      TGI_IMAGE="$2"; shift 2 ;;
    -d | --model-dir )
      MODEL_DIR="$2"; shift 2 ;;
    -m | --model-id )
      MODEL_ID="$2"; shift 2 ;;
    -s | --s3-bucket )
      S3_BUCKET="$2"; shift 2 ;;
    -h | --help )
      usage
      exit 1
      ;;
    -- ) shift; break ;;
    * ) break ;;
  esac
done

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
ABS_MODEL_DIR=`realpath ${MODEL_DIR}`

echo What is your huggingface access token?
read -s AUTH_TOKEN

docker run \
  --rm \
  --entrypoint python \
  --network host \
  -v $ABS_MODEL_DIR:/model \
  -v $SCRIPT_DIR:/code \
  $TGI_IMAGE \
  /code/convert-to-safetensors.py \
    --output-dir /model \
    --model-id $MODEL_ID \
    --auth-token $AUTH_TOKEN

if [ -n "${S3_BUCKET}" ]; then
  echo "Uploading model to ${S3_BUCKET}/${MODEL_ID}"
  source ${SCRIPT_DIR}/fast-s3-transfer.sh -l ${MODEL_DIR} -s ${S3_BUCKET} -m ${MODEL_ID}
fi
