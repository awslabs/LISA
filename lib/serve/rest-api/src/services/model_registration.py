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

"""Model registration service."""
from typing import Any, Protocol

from utils.resources import ModelType, RestApiResource


class RegistryProtocol(Protocol):
    """Protocol for model registry."""

    def get_assets(self, provider: str) -> dict[str, Any]:
        """Get model assets for a provider."""
        ...


class ModelRegistrationService:
    """Service for registering models from configuration."""

    # Supported inference containers
    SUPPORTED_CONTAINERS = ["tgi", "tei", "instructor"]

    def __init__(self, registry: RegistryProtocol):
        """Initialize the service.

        Parameters
        ----------
        registry : RegistryProtocol
            The model registry to use for getting validators
        """
        self.registry = registry

    def create_empty_cache(self) -> dict[str, dict[str, Any]]:
        """Create an empty model cache structure.

        Returns
        -------
        dict[str, dict[str, Any]]
            Empty cache with all required keys
        """
        return {
            ModelType.EMBEDDING: {},
            ModelType.TEXTGEN: {},
            RestApiResource.EMBEDDINGS: {},
            RestApiResource.GENERATE: {},
            RestApiResource.GENERATE_STREAM: {},
            "metadata": {},
            "endpointUrls": {},
        }

    def is_supported_container(self, inference_container: str) -> bool:
        """Check if inference container is supported.

        Parameters
        ----------
        inference_container : str
            The inference container name

        Returns
        -------
        bool
            True if supported, False otherwise
        """
        return inference_container in self.SUPPORTED_CONTAINERS

    def register_model(self, model: dict[str, Any], cache: dict[str, dict[str, Any]]) -> None:
        """Register a single model into the cache.

        Parameters
        ----------
        model : dict[str, Any]
            Model configuration with keys: provider, modelName, modelType, endpointUrl, streaming
        cache : dict[str, dict[str, Any]]
            The cache to update
        """
        provider = model["provider"]
        model_name = model["modelName"]
        model_type = model["modelType"]

        # provider format is `modelHosting.modelType.inferenceContainer`
        # example: "ecs.textgen.tgi"
        parts = provider.split(".")
        if len(parts) != 3:
            return  # Invalid provider format

        inference_container = parts[2]

        # Skip unsupported containers
        if not self.is_supported_container(inference_container):
            return

        # Get default model kwargs from validator
        validator = self.registry.get_assets(provider)["validator"]
        model_kwargs = validator().dict()

        # Build model key
        model_key = f"{provider}.{model_name}"

        # Store endpoint URL
        cache["endpointUrls"][model_key] = model["endpointUrl"]

        # Store metadata
        cache["metadata"][model_key] = {
            "provider": provider,
            "modelName": model_name,
            "modelType": model_type,
            "modelKwargs": model_kwargs,
        }
        if "streaming" in model:
            cache["metadata"][model_key]["streaming"] = model["streaming"]

        # Register by model type and resource
        if model_type == ModelType.EMBEDDING:
            cache[RestApiResource.EMBEDDINGS].setdefault(provider, []).append(model_name)
            cache[ModelType.EMBEDDING].setdefault(provider, []).append(model_name)
        elif model_type == ModelType.TEXTGEN:
            cache[RestApiResource.GENERATE].setdefault(provider, []).append(model_name)
            cache[ModelType.TEXTGEN].setdefault(provider, []).append(model_name)
            if model.get("streaming", False):
                cache[RestApiResource.GENERATE_STREAM].setdefault(provider, []).append(model_name)

    def register_models(self, models: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        """Register multiple models.

        Parameters
        ----------
        models : list[dict[str, Any]]
            List of model configurations

        Returns
        -------
        dict[str, dict[str, Any]]
            The populated cache
        """
        cache = self.create_empty_cache()

        for model in models:
            try:
                self.register_model(model, cache)
            except Exception:  # nosec B112
                # Skip models that fail to register - this is intentional
                # to allow partial registration when some models are misconfigured
                continue

        return cache
