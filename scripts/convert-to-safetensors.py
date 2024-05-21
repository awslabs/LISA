#   Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
#
#   Licensed under the Apache License, Version 2.0 (the "License").
#   You may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

"""
Script that will convert standard pytorch weights to safe tensor weights.

Parameters
----------
--model-id: str = None
    huggingface model id or local model dir
--auth-token: str = None
    huggingface auth token for restricted models
--output-dir: str = None
    directory to output model to
--max-shard-size: str = "2GB"
    maximum size of safetensor shards
"""

import argparse
from pathlib import Path

from transformers import AutoModelForCausalLM, AutoTokenizer

parser = argparse.ArgumentParser()
parser.add_argument("--model-id", help="huggingface model ID or local model dir", default=None)
parser.add_argument("--auth-token", help="huggingface authtoken for restricted models", default=None)
parser.add_argument("--output-dir", help="local directory to output model to", default=None)
parser.add_argument("--max-shard-size", help="maximum size of safetensor shard", default="2GB")
args = parser.parse_args()

# pull down model files from HF Hub if needed
model_dir_fpath = Path(args.output_dir, args.model_id)
if not model_dir_fpath.exists():
    from huggingface_hub import login, snapshot_download

    if args.auth_token:
        login(token=args.auth_token)
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
