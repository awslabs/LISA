"""
Script that will convert standard pytorch weights to safe tensor weights.

Parameters
----------
--model-id: str = None
    huggingface model id or local model dir
--output-dir: str = None
    directory to output model to
--max-shard-size: str = "2GB"
    maximum size of safetensor shards

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""

import argparse
from pathlib import Path

from transformers import AutoModelForCausalLM, AutoTokenizer

parser = argparse.ArgumentParser()
parser.add_argument("--model-id", help="huggingface model ID or local model dir", default=None)
parser.add_argument("--output-dir", help="local directory to output model to", default=None)
parser.add_argument("--max-shard-size", help="maximum size of safetensor shard", default="2GB")
args = parser.parse_args()

# pull down model files from HF Hub if needed
model_dir_fpath = Path(args.output_dir, args.model_id)
if not model_dir_fpath.exists():
    from huggingface_hub import snapshot_download

    print(f"Downloading model ID {args.model_id} to {model_dir_fpath}")
    snapshot_download(
        args.model_id,
        local_dir=model_dir_fpath,
        local_dir_use_symlinks=False,
    )

safetensor_fpaths = list(model_dir_fpath.glob("*.safetensors"))
if len(safetensor_fpaths) < 1:
    print("No safetensors found. Performing model conversion.")
    # load pretrained model
    print(f"Loading {model_dir_fpath}...", end="")
    model = AutoModelForCausalLM.from_pretrained(model_dir_fpath)
    tokenizer = AutoTokenizer.from_pretrained(model_dir_fpath)
    print("done!")

    # save pretrained model into max_shard_size'd safe tensors
    print(
        f"Saving the converted model to {model_dir_fpath} with a maximum shard size of {args.max_shard_size}...",
        end="",
        flush=True,
    )
    model.save_pretrained(model_dir_fpath, max_shard_size=args.max_shard_size, safe_serialization=True)
    tokenizer.save_pretrained(model_dir_fpath)
    print("done!")
else:
    print(f"Found {len(safetensor_fpaths)} safetensors files. Skipping conversion.")
