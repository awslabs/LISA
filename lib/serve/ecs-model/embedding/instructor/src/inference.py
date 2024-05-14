"""
Inference handler.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""
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
