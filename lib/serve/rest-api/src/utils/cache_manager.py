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

"""Model Cache Utilities."""
import threading
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

# Thread locks for cache operations
_REGISTERED_MODELS_LOCK = threading.RLock()
_MODEL_ASSETS_LOCK = threading.RLock()


def get_registered_models_cache() -> Dict[str, Dict[str, Any]]:
    """Get the cache containing the registered models."""
    with _REGISTERED_MODELS_LOCK:
        return REGISTERED_MODELS_CACHE.copy()


def get_model_assets(model_key: str) -> Optional[Tuple[Any, Any]]:
    """Get the cache belonging to the model assets."""
    with _MODEL_ASSETS_LOCK:
        return MODEL_ASSETS_CACHE.get(model_key)


def cache_model_assets(key: str, model_assets: Tuple[Any, Any]) -> None:
    """Cache the specified model assets for the specified key."""
    with _MODEL_ASSETS_LOCK:
        MODEL_ASSETS_CACHE[key] = model_assets


def set_registered_models_cache(models: Dict[str, Dict[str, Any]]) -> None:
    """Set the registered model cache to the specified models value."""
    with _REGISTERED_MODELS_LOCK:
        global REGISTERED_MODELS_CACHE
        REGISTERED_MODELS_CACHE = models
