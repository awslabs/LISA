"""
REST API.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""
from typing import Any, Dict, Optional, Tuple

from .resources import ModelType, RestApiResource

# Cache structure containing different types of information related to registered models.
# - ModelType keys (EMBEDDING, TEXTGEN) are used for quick lookup of models by type.
# - RestApiResource keys (EMBEDDINGS, GENERATE, GENERATE_STREAM) contain models by endpoint.
# - 'metadata' contains detailed information about each model.
# - 'endpointUrls' contains the URLs for model instantiation.
REGISTERED_MODELS_CACHE: Dict[str, Dict[str, Any]] = {
    ModelType.EMBEDDING: {},
    ModelType.TEXTGEN: {},
    RestApiResource.EMBEDDINGS: {},
    RestApiResource.GENERATE: {},
    RestApiResource.GENERATE_STREAM: {},
    "metadata": {},
    "endpointUrls": {},
}
MODEL_ASSETS_CACHE: Dict[str, Tuple[Any, Any]] = {}


def get_registered_models_cache() -> Dict[str, Dict[str, Any]]:
    """Get the cache containing the registered models."""
    return REGISTERED_MODELS_CACHE


def get_model_assets(model_key: str) -> Optional[Tuple[Any, Any]]:
    """Get the cache belonging to the model assets."""
    return MODEL_ASSETS_CACHE.get(model_key, None)


def cache_model_assets(key: str, model_assets: Tuple[Any, Any]) -> None:
    """Cache the specified model assets for the specified key."""
    global MODEL_ASSETS_CACHE
    MODEL_ASSETS_CACHE[key] = model_assets


def set_registered_models_cache(models: Dict[str, Dict[str, Any]]) -> None:
    """Set the registered model cache to the specified models value."""
    global REGISTERED_MODELS_CACHE
    REGISTERED_MODELS_CACHE = models
