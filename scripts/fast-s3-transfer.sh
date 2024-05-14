#!/bin/bash

LOCAL_MODEL_DIR=""
S3_BUCKET=""
MODEL_ID=""
TRANSFER_TYPE="upload"

usage(){
  cat << EOF >&2
Usage: $0
    [ -l | --local-model-dir  - path to the local model directory, e.g. /path/to/models/]
    [ -s | --s3-bucket - s3-bucket name, e.g. my-models-s3-bucket]
    [ -m | --model-id - the model id, e.g. my-model, model files will be/should be at /path/to/models/my-model and s3://my-models-s3-bucket/my-model/]
    [ -d | --download - flag to download instead of upload ]
    [ -h | --help]
EOF
}

# NOTE: This requires GNU getopt.  On Mac OS X and FreeBSD, you have to install this
# separately; see below.
TEMP=$(getopt -o l:s:m:dh --long local-model-dir:,s3-bucket:,model-id:,download,help \
              -- "$@")

if [ $? != 0 ] ; then echo "Terminating..." >&2 ; exit 1 ; fi

# Note the quotes around '$TEMP': they are essential!
eval set -- "$TEMP"

while true; do
  case "$1" in
    -l | --local-model-dir )
      LOCAL_MODEL_DIR="$2"; shift 2 ;;
    -s | --s3-bucket )
      S3_BUCKET="$2"; shift 2 ;;
    -m | --model-id )
      MODEL_ID="$2"; shift 2 ;;
    -d | --download )
      DOWNLOAD=1; shift ;;
    -h | --help )
      usage
      exit 1
      ;;
    -- ) shift; break ;;
    * ) break ;;
  esac
done

if [[ "$DOWNLOAD" == 1 ]];then
  echo "Downloading from: s3://$S3_BUCKET/$MODEL_ID to $LOCAL_MODEL_DIR/$MODEL_ID"
  aws s3 ls s3://$S3_BUCKET/$MODEL_ID/ | awk '{print $4}' | xargs -P10 -I% s5cmd sync s3://$S3_BUCKET/$MODEL_ID/% $LOCAL_MODEL_DIR/$MODEL_ID/
else
  echo "Uploading from $LOCAL_MODEL_DIR/$MODEL_ID to s3://$S3_BUCKET/$MODEL_ID"
  ls $LOCAL_MODEL_DIR/$MODEL_ID | xargs -P10 -I% s5cmd sync $LOCAL_MODEL_DIR/$MODEL_ID/% s3://$S3_BUCKET/$MODEL_ID/
fi
