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

"""Inference handler."""
from typing import Any, Dict

import torch
from InstructorEmbedding import INSTRUCTOR
from sagemaker_inference import decoder


def input_fn(input_data: Any, content_type: Any) -> Any:
    """Process input payload."""
    np_array = decoder.decode(input_data, content_type)  # Converts most types to numpy array
    return np_array.tolist()


def model_fn(model_dir: str) -> INSTRUCTOR:
    """Load model."""
    device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")

    # Load model from local directory
    print(f"Loading model from {model_dir}")
    model = INSTRUCTOR(model_name_or_path=model_dir, device=device)
    return model


def predict_fn(data: Dict[str, Any], model: INSTRUCTOR) -> Any:
    """Get embeddings."""
    instruction = data["instruction"]
    text = data["text"]
    embeddings = model.encode([[instruction, text]])
    return embeddings
