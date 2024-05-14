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

num_safetensors=$( \
    aws --output json \
        --query "length(Contents[?contains(Key, 'safetensor')] || \`[]\`)" \
        s3api list-objects \
            --bucket ${S3_BUCKET} \
            --prefix ${MODEL_ID}/ \
)

if [ $num_safetensors -lt 1 ]
then
    echo "No safetensors found for model: ${MODEL_ID} in bucket: ${S3_BUCKET}."
    exit 1
else
    echo "Found ${num_safetensors} safetensors for model: ${MODEL_ID} in bucket: ${S3_BUCKET}."
fi
