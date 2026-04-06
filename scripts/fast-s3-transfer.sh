#!/usr/bin/env bash

set -euo pipefail

LOCAL_MODEL_DIR=""
S3_BUCKET=""
MODEL_ID=""
DOWNLOAD=0

usage() {
  cat <<EOF >&2
Usage: $0 [options]

Options:
  -l, --local-model-dir DIR   Local model directory path
  -s, --s3-bucket BUCKET      S3 bucket name
  -m, --model-id ID           S3 key prefix / model id
  -d, --download              Download instead of upload
  -h, --help                  Show this help message
EOF
}

die() {
  echo "Error: $*" >&2
  usage
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -l|--local-model-dir)
      [[ $# -ge 2 ]] || die "Missing value for $1"
      LOCAL_MODEL_DIR="$2"
      shift 2
      ;;
    -s|--s3-bucket)
      [[ $# -ge 2 ]] || die "Missing value for $1"
      S3_BUCKET="$2"
      shift 2
      ;;
    -m|--model-id)
      [[ $# -ge 2 ]] || die "Missing value for $1"
      MODEL_ID="$2"
      shift 2
      ;;
    -d|--download)
      DOWNLOAD=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      break
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

[[ -n "$LOCAL_MODEL_DIR" ]] || die "--local-model-dir is required"
[[ -n "$S3_BUCKET" ]] || die "--s3-bucket is required"
[[ -n "$MODEL_ID" ]] || die "--model-id is required"

if [[ "$DOWNLOAD" == 1 ]]; then
  mkdir -p "$LOCAL_MODEL_DIR"
  echo "Downloading from s3://$S3_BUCKET/$MODEL_ID to $LOCAL_MODEL_DIR"
  s5cmd sync "s3://$S3_BUCKET/$MODEL_ID/*" "$LOCAL_MODEL_DIR/"
else
  [[ -d "$LOCAL_MODEL_DIR" ]] || die "Local model directory does not exist: $LOCAL_MODEL_DIR"
  echo "Uploading from $LOCAL_MODEL_DIR to s3://$S3_BUCKET/$MODEL_ID"
  s5cmd sync "$LOCAL_MODEL_DIR/" "s3://$S3_BUCKET/$MODEL_ID/"
fi
