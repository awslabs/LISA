"""
Model registry.

Copyright (C) 2023 Amazon Web Services, Inc. or its affiliates. All Rights Reserved.
This AWS Content is provided subject to the terms of the AWS Customer Agreement
available at http://aws.amazon.com/agreement or other written agreement between
Customer and either Amazon Web Services, Inc. or Amazon Web Services EMEA SARL or both.
"""
from typing import Any, Dict


class ModelRegistry:
    """Registry for model providers."""

    def __init__(self) -> None:
        self.registry: Dict[str, Any] = {}

    def register(self, *, provider: str, adapter: Any, validator: Any) -> None:
        """Register the adapter and validator for the model provider.

        Parameters
        ----------
        provider : str
            Model provider name.

        adapter : Any
            Model adapter.

        validator : Any
            Model kwargs validator.
        """
        self.registry[provider] = {"adapter": adapter, "validator": validator}

    def get_assets(self, provider: str) -> Dict[str, Any]:
        """Get model registry entry."""
        try:
            model_assets = self.registry[provider]
        except KeyError:
            raise KeyError(
                f"Model provider '{provider}' not found in registry. Available providers: "
                f"{', '.join(list(self.registry))}"
            )
        return model_assets  # type: ignore
