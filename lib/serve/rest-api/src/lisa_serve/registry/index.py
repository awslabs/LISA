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

"""Model registry."""
from typing import Any


class ModelRegistry:
    """Registry for model providers."""

    def __init__(self) -> None:
        self.registry: dict[str, Any] = {}

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

    def get_assets(self, provider: str) -> dict[str, Any]:
        """Get model registry entry."""
        try:
            model_assets = self.registry[provider]
        except KeyError:
            raise KeyError(
                f"Model provider '{provider}' not found in registry. Available providers: "
                f"{', '.join(self.registry)}"
            )
        return model_assets  # type: ignore
