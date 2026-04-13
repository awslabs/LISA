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

"""Golden dataset loading and validation for RAG evaluation."""

from .types import GoldenDatasetEntry


def load_golden_dataset(path: str) -> list[GoldenDatasetEntry]:
    """Load and validate a golden dataset from a JSONL file.

    Each line must be a valid JSON object conforming to GoldenDatasetEntry.
    Blank lines are skipped.

    Args:
        path: Filesystem path to a .jsonl file.

    Returns:
        List of validated GoldenDatasetEntry models.

    Raises:
        FileNotFoundError: If path does not exist.
        pydantic.ValidationError: If any line fails validation.
    """
    entries: list[GoldenDatasetEntry] = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(GoldenDatasetEntry.model_validate_json(line))
    return entries
