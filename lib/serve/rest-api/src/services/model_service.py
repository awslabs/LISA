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

"""Service for model operations - follows Single Responsibility Principle."""

import time
from collections import defaultdict
from typing import Any, DefaultDict

from utils.resources import ModelType


class ModelService:
    """Service class for model-related operations.

    This class encapsulates all model listing and description logic,
    making it easy to test without external dependencies.
    """

    def __init__(self, models_cache: dict[str, Any]):
        """Initialize with models cache.

        Parameters
        ----------
        models_cache : dict
            The registered models cache
        """
        self.models_cache = models_cache

    def list_models(self, model_types: list[ModelType]) -> dict[ModelType, dict[str, list[str]]]:
        """List models by type.

        Parameters
        ----------
        model_types : List[ModelType]
            Model types to list

        Returns
        -------
        Dict[ModelType, Dict[str, List[str]]]
            List of model names by model type and provider
        """
        return {model_type: self.models_cache.get(model_type, {}) for model_type in model_types}

    def list_models_openai_format(self) -> dict[str, Any]:
        """List models in OpenAI-compatible format.

        Returns
        -------
        Dict[str, Any]
            OpenAI-compatible response with text generation models
        """
        textgen_models = self.models_cache.get(ModelType.TEXTGEN, {})

        model_payload: list[dict[str, Any]] = []
        for provider, models in textgen_models.items():
            model_payload.extend(
                {"id": f"{model} ({provider})", "object": "model", "created": int(time.time()), "owned_by": "LISA"}
                for model in models
            )

        return {"data": model_payload, "object": "list"}

    def get_model_metadata(self, provider: str, model_name: str) -> dict[str, Any] | None:
        """Get metadata for a specific model.

        Parameters
        ----------
        provider : str
            Model provider name
        model_name : str
            Model name

        Returns
        -------
        Dict[str, Any] | None
            Model metadata or None if not found
        """
        model_key = f"{provider}.{model_name}"
        metadata_cache = self.models_cache.get("metadata", {})
        result = metadata_cache.get(model_key)
        return result if result is not None else None

    def describe_models(self, model_types: list[ModelType]) -> DefaultDict[str, DefaultDict[str, dict[str, Any]]]:
        """Get detailed metadata for models by type.

        Parameters
        ----------
        model_types : List[ModelType]
            Model types to describe

        Returns
        -------
        DefaultDict[str, DefaultDict[str, Dict[str, Any]]]
            Model metadata by type, provider, and name
        """
        registered_models = self.list_models(model_types)
        metadata_cache = self.models_cache.get("metadata", {})
        response: DefaultDict[str, DefaultDict[str, dict[str, Any]]] = defaultdict(lambda: defaultdict(dict))

        for model_type, providers in registered_models.items():
            response[model_type] = {}  # type: ignore
            providers = providers or {}
            for provider, model_names in providers.items():
                response[model_type][provider] = [
                    metadata_cache[f"{provider}.{model_name}"]
                    for model_name in model_names
                    if f"{provider}.{model_name}" in metadata_cache
                ]  # type: ignore

        return response
