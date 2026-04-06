#!/usr/bin/env python3
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

"""Print self-hosted model names required for integration testing as a JSON array.

Reads deploy_models and deploy_embedded_models from integration_definitions.py and
outputs the HuggingFace model_name for each entry (e.g. "meta-llama/Llama-3.2-3B-Instruct").
Used by scripts/run-integration-tests.mjs to preflight-check S3 before deploying models.

Usage:
    python test/python/list-integ-models.py
"""

import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from integration_definitions import (
    deploy_embedded_models,
    deploy_models,
    EMBEDDED_MODEL_DEFINITIONS,
    MODEL_DEFINITIONS,
)

names = [MODEL_DEFINITIONS[m]["model_name"] for m in deploy_models if m in MODEL_DEFINITIONS]
names += [
    EMBEDDED_MODEL_DEFINITIONS[m]["model_name"] for m in deploy_embedded_models if m in EMBEDDED_MODEL_DEFINITIONS
]

print(json.dumps(names))
