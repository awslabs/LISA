#!/usr/bin/env bash

set -euo pipefail

ACCESS_TOKEN=""
MODEL_DIR=""
MODEL_ID=""
S3_BUCKET=""
FORCE_CONVERT="false"
UPLOAD_PREFIX=""
SKIP_UPLOAD="false"

usage() {
  cat <<EOF >&2
Usage: $0 [options]

Options:
  -a, --access-token TOKEN   Hugging Face access token for restricted models
  -d, --model-dir DIR        Local directory used for model storage
  -m, --model-id ID          Hugging Face model ID or path to local model dir
  -s, --s3-bucket BUCKET     S3 bucket name
  -p, --upload-prefix PREFIX Optional S3 key prefix before model path
      --force-convert        Force conversion to safetensors
      --skip-upload          Prepare locally but do not upload
  -h, --help                 Show this help message
EOF
}

die() {
  echo "Error: $*" >&2
  usage
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -a|--access-token)
      [[ $# -ge 2 ]] || die "Missing value for $1"
      ACCESS_TOKEN="$2"
      shift 2
      ;;
    -d|--model-dir)
      [[ $# -ge 2 ]] || die "Missing value for $1"
      MODEL_DIR="$2"
      shift 2
      ;;
    -m|--model-id)
      [[ $# -ge 2 ]] || die "Missing value for $1"
      MODEL_ID="$2"
      shift 2
      ;;
    -s|--s3-bucket)
      [[ $# -ge 2 ]] || die "Missing value for $1"
      S3_BUCKET="$2"
      shift 2
      ;;
    -p|--upload-prefix)
      [[ $# -ge 2 ]] || die "Missing value for $1"
      UPLOAD_PREFIX="$2"
      shift 2
      ;;
    --force-convert)
      FORCE_CONVERT="true"
      shift
      ;;
    --skip-upload)
      SKIP_UPLOAD="true"
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

[[ -n "$MODEL_DIR" ]] || die "--model-dir is required"
[[ -n "$MODEL_ID" ]] || die "--model-id is required"

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
mkdir -p "$MODEL_DIR"
ABS_MODEL_DIR="$(realpath "$MODEL_DIR")"

# Sanitize a model ID into a directory name, but keep original ID for S3 path.
MODEL_BASENAME="${MODEL_ID##*/}"
LOCAL_MODEL_PATH="${ABS_MODEL_DIR}/${MODEL_BASENAME}"

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

need_python_dep() {
  local mod="$1"
  python3 - <<PY >/dev/null 2>&1
import importlib
import sys
sys.exit(0 if importlib.util.find_spec("${mod}") else 1)
PY
}

download_hf_model() {
  local model_id="$1"
  local output_dir="$2"

  echo "Downloading Hugging Face model: ${model_id}"
  mkdir -p "$output_dir"

  export HF_HUB_DISABLE_TELEMETRY=1
  if [[ -n "${ACCESS_TOKEN}" ]]; then
    export HUGGINGFACE_HUB_TOKEN="${ACCESS_TOKEN}"
    export HF_TOKEN="${ACCESS_TOKEN}"
  fi

  python3 - <<PY
import os
from huggingface_hub import snapshot_download

model_id = ${model_id@Q}
output_dir = ${output_dir@Q}
token = os.environ.get("HUGGINGFACE_HUB_TOKEN") or os.environ.get("HF_TOKEN")

snapshot_download(
    repo_id=model_id,
    local_dir=output_dir,
    local_dir_use_symlinks=False,
    token=token,
    resume_download=True,
)
print(f"Downloaded to {output_dir}")
PY
}

copy_local_model() {
  local src="$1"
  local dst="$2"

  echo "Using local model path: ${src}"
  rm -rf "$dst"
  mkdir -p "$dst"
  cp -R "$src"/. "$dst"/
}

has_safetensors() {
  local dir="$1"
  find "$dir" -maxdepth 1 -type f \( -name "*.safetensors" -o -name "*.safetensors.index.json" \) | grep -q .
}

has_pytorch_bin() {
  local dir="$1"
  find "$dir" -maxdepth 1 -type f \( -name "pytorch_model.bin" -o -name "pytorch_model-*.bin" -o -name "*.bin.index.json" \) | grep -q .
}

convert_to_safetensors() {
  local model_path="$1"

  echo "Converting model to safetensors in: ${model_path}"

  python3 - <<PY
import os
import shutil
from pathlib import Path

from transformers import AutoModelForCausalLM, AutoModel, AutoConfig
from safetensors.torch import save_file
import torch

model_path = Path(${model_path@Q})

def save_state_dict_as_safetensors(state_dict, out_file):
    contiguous = {}
    for k, v in state_dict.items():
        if isinstance(v, torch.Tensor):
            contiguous[k] = v.detach().cpu().contiguous()
    save_file(contiguous, str(out_file))

config = AutoConfig.from_pretrained(model_path, trust_remote_code=True)

loaded = False
model = None
last_err = None

for cls in (AutoModelForCausalLM, AutoModel):
    try:
        model = cls.from_pretrained(
            model_path,
            trust_remote_code=True,
            torch_dtype="auto",
            low_cpu_mem_usage=True,
        )
        loaded = True
        break
    except Exception as e:
        last_err = e

if not loaded:
    raise RuntimeError(f"Failed to load model for conversion: {last_err}")

state_dict = model.state_dict()
out_file = model_path / "model.safetensors"
save_state_dict_as_safetensors(state_dict, out_file)

# Keep config/tokenizer files. Remove common pytorch weight files after successful conversion.
for pattern in ["pytorch_model.bin", "pytorch_model-*.bin", "*.bin.index.json"]:
    for p in model_path.glob(pattern):
        try:
            p.unlink()
        except IsADirectoryError:
            shutil.rmtree(p)

print(f"Wrote safetensors file: {out_file}")
PY
}

upload_to_s3() {
  local local_dir="$1"
  local bucket="$2"
  local model_key="$3"
  local prefix="$4"

  local s3_key
  if [[ -n "$prefix" ]]; then
    s3_key="${prefix%/}/${model_key}"
  else
    s3_key="${model_key}"
  fi

  echo "Uploading model to s3://${bucket}/${s3_key}"
  bash "${SCRIPT_DIR}/fast-s3-transfer.sh" \
    -l "$local_dir" \
    -s "$bucket" \
    -m "$s3_key"
}

echo "Preparing model: ${MODEL_ID}"

if [[ -d "$MODEL_ID" ]]; then
  copy_local_model "$MODEL_ID" "$LOCAL_MODEL_PATH"
else
  download_hf_model "$MODEL_ID" "$LOCAL_MODEL_PATH"
fi

if [[ "$FORCE_CONVERT" == "true" ]]; then
  echo "Force convert enabled."
  convert_to_safetensors "$LOCAL_MODEL_PATH"
else
  if has_safetensors "$LOCAL_MODEL_PATH"; then
    echo "Model already contains safetensors. No conversion required."
  elif has_pytorch_bin "$LOCAL_MODEL_PATH"; then
    echo "Model contains PyTorch .bin weights and no safetensors. Converting."
    convert_to_safetensors "$LOCAL_MODEL_PATH"
  else
    echo "No known PyTorch weight files requiring conversion were found. Uploading as-is."
  fi
fi

if [[ "$SKIP_UPLOAD" == "true" ]]; then
  echo "Skipping upload as requested."
else
  [[ -n "$S3_BUCKET" ]] || die "--s3-bucket is required unless --skip-upload is used"
  upload_to_s3 "$LOCAL_MODEL_PATH" "$S3_BUCKET" "$MODEL_ID" "$UPLOAD_PREFIX"
fi

echo "Done."