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

"""CLI entry point for RAG evaluation.

Usage:
    python -m lisapy.evaluation --config eval_config.yaml --dataset golden-dataset.jsonl
"""

import argparse
import logging
import sys

from .config import load_eval_config
from .runner import run_evaluation


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run RAG evaluation across configured backends.",
        prog="python -m lisapy.evaluation",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to evaluation config YAML file.",
    )
    parser.add_argument(
        "--dataset",
        required=True,
        help="Path to golden dataset JSONL file.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging.",
    )
    args = parser.parse_args()

    # Configure logging
    level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)

    try:
        config = load_eval_config(args.config)
        run_evaluation(config, args.dataset)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            raise
        sys.exit(1)


if __name__ == "__main__":
    main()
